# BERTweet sarcasm loader (your fully fine-tuned model)
from pathlib import Path
from typing import Optional
import os, torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

ROOT = Path(__file__).resolve().parents[1]
SARC_DIR = ROOT / "models" / "sarcasm_berttweet"

def _device():
    if torch.backends.mps.is_available():
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        return torch.device("mps")
    return torch.device("cpu")

class SarcasmModel:
    def __init__(self, model_dir: Optional[str] = None):
        path = Path(model_dir) if model_dir else SARC_DIR
        assert path.exists(), f"Missing sarcasm model at {path}"
        self.tok = AutoTokenizer.from_pretrained(str(path), use_fast=True)
        self.mdl = AutoModelForSequenceClassification.from_pretrained(str(path)).eval().to(_device())

    def prob(self, text: str, max_len: int = 128) -> float:
        x = self.tok(text, return_tensors="pt", truncation=True, max_length=max_len).to(self.mdl.device)
        with torch.no_grad():
            p = self.mdl(**x).logits[0].softmax(-1).tolist()
        return float(p[1])  # 1 = sarcasm
