# 🤖 PeerSupportBot

> An AI-powered Discord bot designed to foster safe, respectful, and supportive online communities.  
> Combines **toxic comment detection**, **sarcasm understanding**, and **empathetic moderation policies** into a transparent, agent-based system.

---

## 📖 Overview

PeerSupportBot is not just another moderation bot. It’s an **AI companion** that understands context, balances safety with empathy, and provides transparency through reporting.  

It can:
- Redact harmful or extreme messages
- Privately DM users with empathetic warnings
- Detect crisis/self-harm language
- Generate detailed moderation reports for accountability

---

## ✨ Features

- 🔎 **Real-time moderation** (toxicity, harassment, slurs, threats, crisis/self-harm)  
- 📝 **Message redaction** (delete or replace with a neutral placeholder)  
- 📩 **Private warnings via DM**, including crisis resources when needed  
- 📊 **Violation tracking** (escalates to final warnings after 5 strikes)  
- 📅 **Reports**:  
  - Daily (23:59 IST)  
  - Rolling (every 50 incidents)  
  - On-demand (`/report` slash command)  
- 🧩 **Hybrid decision layer**:  
  - ML models (toxicity + sarcasm)  
  - Policy overrides (regex for crisis and extreme words)  
- 🛡️ **LangGraph multi-agent pipeline** for modularity and clarity  

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
    H --> I[Reports: Daily · Rolling · Special]
