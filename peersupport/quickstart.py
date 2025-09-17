from __future__ import annotations
import os, re, json
from typing import Tuple, Dict, List

from dotenv import load_dotenv
from loguru import logger

import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from peft import PeftModel
from openai import OpenAI

# ========== ENV ==========
load_dotenv()
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Paths: set these in .env
PATH_SARCASM = os.getenv("SARCASM_MODEL_PATH", "")
PATH_TOX_BASE = os.getenv("TOXICITY_BASE_MODEL", "distilbert-base-uncased")
PATH_TOX_LORA = os.getenv("TOXICITY_ADAPTER_PATH", "")  # can be empty

assert OPENAI_API_KEY, "OPENAI_API_KEY is empty in .env"
assert PATH_SARCASM, "SARCASM_MODEL_PATH is empty in .env"

DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
logger.info(f"Using device: {DEVICE}")

# ========== Sarcasm (binary or 2-class) ==========
class SarcasmModel:
    def __init__(self, path: str):
        logger.info(f"Loading sarcasm model: {path}")
        self.tok = AutoTokenizer.from_pretrained(path, use_fast=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(path)
        self.model.to(DEVICE).eval()

    @torch.inference_mode()
    def score(self, text: str) -> float:
        enc = self.tok(text, return_tensors="pt", truncation=True, max_length=128)
        enc = {k: v.to(DEVICE) for k, v in enc.items()}
        logits = self.model(**enc).logits
        if logits.numel() == 1:  # single logit (sigmoid)
            return float(torch.sigmoid(logits)[0].item())
        # assume 2-class softmax with index 1 = sarcastic
        return float(torch.softmax(logits, dim=-1)[0, 1].item())

# ========== Toxicity (6-headed Jigsaw) ==========
JIGSAW_LABELS: List[str] = [
    "toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate"
]
NUM_LABELS = 6

class ToxicityModel6:
    def __init__(self, base: str, adapter: str | None = None):
        logger.info(f"Loading toxicity base={base} adapter={adapter or '(none)'}")
        self.tok = AutoTokenizer.from_pretrained(base)
        base_model = AutoModelForSequenceClassification.from_pretrained(
            base, num_labels=NUM_LABELS, ignore_mismatched_sizes=True
        )
        # ensure head has 6 out features
        hidden = getattr(base_model.config, "dim", getattr(base_model.config, "hidden_size", 768))
        if not hasattr(base_model, "classifier") or getattr(base_model.classifier, "out_features", NUM_LABELS) != NUM_LABELS:
            base_model.classifier = nn.Linear(hidden, NUM_LABELS)

        if adapter:
            model = PeftModel.from_pretrained(base_model, adapter)
        else:
            model = base_model

        self.model = model.to(DEVICE).eval()

    @torch.inference_mode()
    def scores(self, text: str) -> Dict[str, float]:
        enc = self.tok(text, return_tensors="pt", truncation=True, max_length=128)
        enc = {k: v.to(DEVICE) for k, v in enc.items()}
        logits = self.model(**enc).logits  # [1, 6]
        probs = torch.sigmoid(logits)[0].tolist()  # multi-label
        return {label: float(p) for label, p in zip(JIGSAW_LABELS, probs)}

# ========== Policy ==========
# seriousness ↑ when toxicity is high AND sarcasm is low
def seriousness_score(toxicity_max: float, sarcasm: float) -> float:
    """
    seriousness = toxicity_max * (1 - sarcasm)
    - High toxicity (-> 1) pushes seriousness up
    - High sarcasm (-> 1) pushes seriousness down
    """
    s = float(toxicity_max) * (1.0 - float(sarcasm))
    return max(0.0, min(1.0, s))

# Only serious (no playful path)
THRESHOLDS = {
    "tox_high": 0.85,
    "sarcasm_low": 0.40,
    "seriousness_high": 0.60,
}

# Crisis detection (self-harm / severe distress)
CRISIS_PATTERNS = [
    r"\bi (?:want|going|plan) to (?:kill|harm|hurt) (?:myself|me)\b",
    r"\b(?:suicide|kill myself|end my life)\b",
    r"\b(?:i(?:'m| am) (?:done|hopeless)|i can't go on)\b",
]
CRISIS_RE = re.compile("|".join(CRISIS_PATTERNS), re.IGNORECASE)

def is_crisis(text: str) -> bool:
    return bool(CRISIS_RE.search(text or ""))

def decide_action(sarcasm: float, tox_scores: Dict[str, float], text: str = "") -> Tuple[str, Dict[str, float]]:
    """
    Returns action:
      - 'crisis'  → heartfelt resources DM
      - 'serious' → serious warning DM
      - 'none'
    """
    if is_crisis(text):
        return "crisis", {"tox_max": max(tox_scores.values()) if tox_scores else 0.0, "seriousness": 1.0}

    tox_max = max(tox_scores.values()) if tox_scores else 0.0
    serious = seriousness_score(tox_max, sarcasm)

    if (tox_max >= THRESHOLDS["tox_high"]
        and sarcasm <= THRESHOLDS["sarcasm_low"]
        and serious >= THRESHOLDS["seriousness_high"]):
        return "serious", {"tox_max": tox_max, "seriousness": serious}

    return "none", {"tox_max": tox_max, "seriousness": serious}

# ========== OpenAI responders (serious + crisis) ==========
client = OpenAI(api_key=OPENAI_API_KEY)

# Simple local Resource RAG
RES_PATH = os.path.join(os.getcwd(), "app", "resources.json")
DEFAULT_IITG = "https://online.iitg.ac.in/chw/vdstudentspecial.jsp"

try:
    with open(RES_PATH, "r", encoding="utf-8") as f:
        RESOURCES = json.load(f)
except Exception:
    RESOURCES = {
        "self_harm": [
            {"name": "IITG Psychiatrist Appointments", "url": DEFAULT_IITG},
            {"name": "Kiran Mental Health Helpline (24x7)", "url": "1800-599-0019"},
            {"name": "AASRA 24x7 Helpline", "url": "9152987821"},
        ]
    }

def _resource_block(kind: str = "self_harm") -> str:
    items = RESOURCES.get(kind, [])[:3]
    if not items:
        return f"Campus support: {DEFAULT_IITG}"
    return "\n".join([f"- {it['name']}: {it['url']}" for it in items])

SYS_SERIOUS = (
    "You are a respectful but firm student community assistant. "
    "When a message is highly offensive or threatening, send a brief, serious, policy-aligned warning in 1–2 sentences. "
    "Be clear about community guidelines and ask the sender to stop. "
    "Suggest a short cool-down. Do NOT provide medical advice."
)

SYS_CRISIS = (
    "You are a campus safety assistant. In 1–2 compassionate sentences, acknowledge the distress and point to immediate resources. "
    "Do not diagnose or provide therapy. Encourage reaching out now."
)

def craft_serious_reply(context: str, sarcasm: float, tox_max: float, seriousness: float) -> str:
    # templated fallback on error
    fallback = "Please stop — this violates our community guidelines. Take a short break and return respectfully."
    try:
        out = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYS_SERIOUS},
                {"role": "user", "content":
                    f"Context: {context}\n"
                    f"Scores: toxicity_max={tox_max:.2f}, sarcasm={sarcasm:.2f}, seriousness={seriousness:.2f}\n"
                    "Write a brief serious warning (1–2 sentences)."
                },
            ],
            temperature=0.3,
            max_tokens=50,
        )
        return out.choices[0].message.content.strip()
    except Exception:
        return fallback

def craft_crisis_reply(context: str) -> str:
    resources = _resource_block("self_harm")
    fallback = (
        "You matter, and help is available right now. Consider reaching out:\n" + resources
    )
    try:
        out = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYS_CRISIS},
                {"role": "user", "content":
                    f"Context: {context}\n"
                    f"Include these resources as bullet points:\n\n{resources}"
                },
            ],
            temperature=0.2,
            max_tokens=70,
        )
        return out.choices[0].message.content.strip()
    except Exception:
        return fallback

# ========== Main loop ==========
if __name__ == "__main__":
    # Load models
    sarcasm_model = SarcasmModel(PATH_SARCASM)
    tox_model = ToxicityModel6(PATH_TOX_BASE, PATH_TOX_LORA or None)

    print("\nType a message and press Enter (or type 'exit' to quit).")
    print("Policy: act ONLY when toxicity is high & sarcasm low (serious), or crisis language is present.\n")

    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or text.lower() == "exit":
            break

        # Scores
        s = sarcasm_model.score(text)          # 0..1
        tox = tox_model.scores(text)           # dict of 6 labels

        action, meta = decide_action(s, tox, text=text)
        tox_max = meta["tox_max"]
        serious = meta["seriousness"]

        # Pretty print
        top3 = sorted(tox.items(), key=lambda kv: kv[1], reverse=True)[:3]
        top3_str = ", ".join([f"{k}={v:.2f}" for k, v in top3])
        print(f"sarcasm={s:.2f} | tox_max={tox_max:.2f} | seriousness={serious:.2f} → action={action}")
        print(f"tox detail: {top3_str}")

        if action == "serious":
            reply = craft_serious_reply(text, s, tox_max, serious)
            print(f"SERIOUS → {reply}\n")
        elif action == "crisis":
            reply = craft_crisis_reply(text)
            print(f"CRISIS → {reply}\n")
        else:
            print("No action taken.\n")
