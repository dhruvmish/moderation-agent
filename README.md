#Name - Dhruv Mishra 

> Roll No. - 230106022
> Institute - IIT Guwahati
> Department - Biosciences and Bioengineering
> Role - Data Scientist

# 🤖 PeerSupportBot

> An AI-powered Discord companion that keeps communities safe **and** humane.  
> It combines fine-tuned toxicity and sarcasm models with clear policy rules, message redaction, empathetic DMs, violation tracking, and transparent reporting.

<div align="center">

![Discord](https://img.shields.io/badge/Discord-Bot-7289da?style=for-the-badge&logo=discord&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=for-the-badge&logo=python&logoColor=white)
![AI](https://img.shields.io/badge/AI-Powered-ff6b6b?style=for-the-badge&logo=brain&logoColor=white)
![License](https://img.shields.io/badge/License-Educational-green?style=for-the-badge)

</div>

---

## 📋 Table of Contents

- [🎯 Overview](#-overview)
- [🎯 Goals & Principles](#-goals--principles)
- [🏗️ System Architecture](#️-system-architecture)
- [🤖 Models & Why I Chose Them](#-models--why-i-chose-them)
- [📊 The Seriousness Score (Math Explained)](#-the-seriousness-score-math-explained)
- [🔗 Discord Integration](#-discord-integration)
- [📈 Reports & Accountability](#-reports--accountability)
- [🚀 Getting Started](#-getting-started)
- [⚙️ Configuration](#️-configuration)
- [🏃 Running the Bot](#-running-the-bot)
- [🧪 Testing the Policy](#-testing-the-policy)
- [📊 Evaluation](#-evaluation)
- [💾 Data & Storage](#-data--storage)
- [🛡️ Safety & Ethics](#️-safety--ethics)
- [🔧 Troubleshooting](#-troubleshooting)
- [🗺️ Roadmap](#️-roadmap)
- [📜 License](#-license)

---

## 🎯 Overview

PeerSupportBot isn't a blunt filter. It's a **supportive agent** that understands context (sarcasm, slang, banter), reacts decisively to serious harm (slurs, threats, sexual violence), and treats people with empathy. The bot:

- **🚫 Redacts** harmful messages (delete or replace with a neutral notice)
- **💬 DMs** authors with clear explanations and crisis resources when needed
- **📊 Tracks** violations, issues a **final warning** after 5, and generates **reports**
- **🧠 Uses** a **seriousness score** that blends model signals with policy rules for reliable, human-centered outcomes

---

## 🎯 Goals & Principles

- **🛡️ Safety first, with empathy** - Don't just delete; explain and support
- **🎯 Precision over bluntness** - Understand sarcasm and reduce false positives on everyday banter
- **📊 Transparency** - Log incidents, generate daily/rolling/special reports
- **🔧 Modularity** - Clear agents: Sentinel (detect), Triage (decide), Responder (act), Archivist (log)

---

## 🏗️ System Architecture

### High-Level Flow

```mermaid
flowchart TD
    A[📨 Incoming Message] --> B[🛡️ Sentinel: Toxicity + Sarcasm]
    B --> C[⚖️ Triage: Seriousness + Rules]
    C -->|🚨 Crisis| D[💬 Responder: Redact + DM Crisis Resources]
    C -->|⚠️ Serious| E[💬 Responder: Redact + DM Warning]
    C -->|📝 Moderate| F[💬 Responder: Redact + Softer DM]
    C -->|✅ None| G[📜 Archivist: Log Only]
    D --> H[📜 Archivist: DB + Reports]
    E --> H
    F --> H
    G --> H
    H --> I[📊 Reports: Daily · Rolling · Special]
