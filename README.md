# 🤖 PeerSupportBot

> An AI-powered Discord bot designed to foster safe, respectful, and supportive online communities.  
> Combines **toxic comment detection**, **sarcasm understanding**, and **empathetic moderation policies** into a transparent, agent-based system.

---

## 📖 Overview
PeerSupportBot is not just another moderation bot. It’s an **AI companion** that understands context, balances safety with empathy, and provides transparency through reporting.  
It can redact harmful messages, privately DM users, detect crisis/self-harm language, and generate detailed reports for moderators.

---

## ✨ Features
- 🔎 **Real-time moderation** (toxicity, harassment, slurs, threats, crisis/self-harm).
- 📝 **Message redaction** (delete or replace with a neutral placeholder).
- 📩 **Private warnings via DM**, including crisis resources when needed.
- 📊 **Violation tracking** (with escalation to final warnings after 5 strikes).
- 📅 **Reports**:
  - Daily reports (23:59 IST).
  - Rolling reports every 50 incidents.
  - On-demand `/report` slash command.
- 🧩 **Hybrid decision layer**:
  - ML models (toxicity + sarcasm).
  - Policy overrides (regex for crisis and extreme words).
- 🛡️ **LangGraph multi-agent pipeline** for modularity.

---

## 🏗️ Architecture

### High-Level Diagram
```mermaid
flowchart TD
    A[Incoming Message] --> B[Sentinel: Toxicity + Sarcasm Models]
    B --> C[Triage: Compute Seriousness + Policy Rules]
    C -->|Crisis detected| D[Responder: Redact + DM Crisis Resources]
    C -->|Serious toxicity| E[Responder: Redact + DM Warning]
    C -->|Moderate toxicity| F[Responder: Redact + Softer Warning]
    C -->|No action| G[Archivist: Log Only]
    D --> H[Archivist: Log Incident + DB + Report]
    E --> H
    F --> H
    G --> H
    H --> I[Reports (Daily / Rolling / Special)]
---

## ⚙️ Components

### 🛡️ Sentinel (Detection Agent)
- Runs **DistilBERT + LoRA** for multi-label toxicity (toxic, severe_toxic, obscene, threat, insult, identity_hate).
- Runs **BERTweet (fine-tuned)** for sarcasm probability.
- **Goal:** Capture both surface-level toxicity and hidden sarcasm.

### ⚖️ Triage (Decision Agent)
- Computes **seriousness score** (weighted toxicity labels + sarcasm relief + user/channel context).
- Applies **policy overrides** for crisis/self-harm and extreme words (*rape, kill, n-word, “fuck you”*).
- **Goal:** Ensure context-aware, cautious classification.

### 💬 Responder (Interaction Agent)
- Executes chosen actions:
  - **Redact message**.
  - **DM user** with explanation or crisis resources.
  - **Final warnings** in DM + channel after 5 violations.
- **Goal:** Provide moderation that feels **empathetic, not robotic**.

### 📜 Archivist (Logging & Reporting Agent)
- Persists every incident in SQLite.
- Generates **daily, rolling, and special user reports**.
- **Goal:** Ensure transparency and moderator accountability.

---

## ⚖️ Policy Logic
- **Crisis regex:** Immediate redaction + crisis DM.
- **Extreme words:** Always redacted regardless of model scores.
- **Seriousness scoring:** Weighted mix of toxicity + sarcasm relief.
- **Decision thresholds:**
  - Serious (≥ 0.65 seriousness or tox_max ≥ 0.8).
  - Warn (≥ 0.45 seriousness).
  - Log only (below thresholds).

---

## 📊 Evaluation

### Model-Level
- **Toxicity (DistilBERT-LoRA):** AUPRC, ROC-AUC, F1@best threshold, per-label confusion matrices.
- **Sarcasm (BERTweet):** AUPRC, ROC-AUC, F1, confusion matrix.

### Policy-Level
- Precision/recall/F1 for **Redact**, **Warn**, **None** actions.
- Stress-tested on adversarial phrases (*rape, kill him, nigga, fuck you*).
- Benign control set (*“this exam is stupid”*) to measure false positives.

---

## 🚀 Getting Started

### 1. Clone & Setup
```bash
git clone https://github.com/<your-username>/PeerSupportBot.git
cd PeerSupportBot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
