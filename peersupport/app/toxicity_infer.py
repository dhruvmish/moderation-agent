# M1-safe toxicity loader (LoRA + head + thresholds)
from pathlib import Path
from typing import Dict
import os, json, numpy as np, torch
from transformers import AutoConfig, AutoTokenizer, AutoModelForSequenceClassification
from peft import PeftModel

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_DIR = ROOT / "models" / "toxic_lora"
BASE_DIR    = ROOT / "models" / "toxic_base"

def _device():
    if torch.backends.mps.is_available():
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        return torch.device("mps")
    return torch.device("cpu")

class ToxicModel:
    def __init__(self):
        assert ADAPTER_DIR.exists(), f"Missing {ADAPTER_DIR}"
        labels = json.load(open(ADAPTER_DIR / "labels.json"))["labels"]
        self.labels = labels
        self.thresholds = {k: 0.5 for k in labels}
        thr_file = ADAPTER_DIR / "thresholds.json"
        if thr_file.exists():
            try:
                self.thresholds = json.load(open(thr_file))["thresholds"]
            except Exception:
                pass

        cfg = AutoConfig.from_pretrained(
            str(BASE_DIR if BASE_DIR.exists() else "distilbert-base-uncased"),
            num_labels=len(labels),
            id2label={i:k for i,k in enumerate(labels)},
            label2id={k:i for i,k in enumerate(labels)},
            problem_type="multi_label_classification",
        )
        self.tok = AutoTokenizer.from_pretrained(str(ADAPTER_DIR), use_fast=True)
        base = AutoModelForSequenceClassification.from_pretrained(
            str(BASE_DIR if BASE_DIR.exists() else "distilbert-base-uncased"), config=cfg
        )
        mdl = PeftModel.from_pretrained(base, str(ADAPTER_DIR)).eval()
        head = ADAPTER_DIR / "classifier_head.bin"
        if head.exists():
            sd = torch.load(head, map_location="cpu")
            mdl.base_model.classifier.load_state_dict(sd)
        self.mdl = mdl.to(_device())

    def probs(self, text: str, max_len: int = 256) -> Dict[str, float]:
        x = self.tok(text, return_tensors="pt", truncation=True, max_length=max_len).to(self.mdl.device)
        with torch.no_grad():
            logits = self.mdl(**x).logits[0].float().cpu().numpy()
        p = 1 / (1 + np.exp(-logits))
        return {k: float(v) for k, v in zip(self.labels, p)}

    def flags(self, probs: Dict[str, float]):
        return [k for k, v in probs.items() if v >= self.thresholds.get(k, 0.5)]
