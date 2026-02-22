# Investment Intelligence Daily Briefing System

A personal agentic workflow that delivers a formatted daily email covering the US equity market — bond yields, top news, earnings alerts, price threshold alerts, stock-specific news, and upcoming tech IPOs — every morning at 8 AM Pacific.

Built with Python + Claude Code skills. No subscription fees; data is sourced from free APIs (yfinance, Groq, stockanalysis.com).

---

## Agents / Skills

| Slash command        | Script                        | What it does |
|----------------------|-------------------------------|--------------|
| `/bond-yield`        | `agents/bond_yield.py`        | 10-year Treasury yield, daily Δ in bps, investor context |
| `/daily-news`        | `agents/daily_news.py`        | Top 3 market-moving headlines ≤200 words (Groq) |
| `/earnings-reminder` | `agents/earnings_reminder.py` | T-2 alert when watchlist stock earns in ≤2 days |
| `/price-alerts`      | `agents/price_alerts.py`      | Alert when price crosses configured up/down threshold |
| `/ipo-scout`         | `agents/ipo_scout.py`         | Upcoming tech IPOs, ⭐ flags new since last run |
| `/stock-summary`     | `agents/stock_summary.py`     | ≤3 impactful bullets for ALAB & Gartner with 📈/📉 + links |
| `/benchmark`         | `agents/benchmark.py`         | LLM-as-judge scores all agents (GPT-4o-mini, 1–5 rubric) |

All agents are combined into a single HTML + plain-text email by `agents/daily_report.py`.

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

Copy the template and fill in your values:

```bash
cp config/email_config.template.json config/email_config.json
```

Edit `config/email_config.json`:

| Field | How to get it |
|-------|--------------|
| `sender_email` / `recipient_email` | Your Gmail address |
| `sender_password` | Gmail → Account → Security → 2-Step Verification → App Passwords |
| `groq_api_key` | Free at [console.groq.com](https://console.groq.com) |
| `openai_api_key` | platform.openai.com/api-keys — used only for `/benchmark` |

### 3. Customize your watchlist and thresholds

- `config/watchlist.json` — tickers for earnings alerts
- `config/thresholds.json` — price alert levels per ticker

### 4. Test

```bash
python agents/daily_report.py
```

You should receive an email within 30 seconds.

### 5. Schedule (Windows)

Create a Task Scheduler job:
- **Program:** `python`
- **Arguments:** `C:\path\to\investment-agents\agents\daily_report.py`
- **Trigger:** Daily at 8:00 AM (your local timezone)

---

## File Structure

```
investment-agents/
├── agents/
│   ├── bond_yield.py              # Agent 1 — Treasury yield
│   ├── daily_news.py              # Agent 2 — Market news (Groq)
│   ├── earnings_reminder.py       # Agent 3 — Earnings T-2 alert
│   ├── price_alerts.py            # Agent 4 — Price thresholds
│   ├── ipo_scout.py               # Agent 5 — Tech IPO scanner
│   ├── stock_summary.py           # Agent 6 — ALAB & Gartner news
│   ├── daily_report.py            # Orchestrator + email sender
│   └── benchmark.py               # LLM-as-judge benchmark
├── config/
│   ├── email_config.template.json # Copy to email_config.json and fill in secrets
│   ├── watchlist.json             # Tickers for earnings alerts
│   ├── thresholds.json            # Price alert levels per ticker
│   └── ipo_config.json            # Tech keywords for IPO filter
├── state/                         # Auto-generated at runtime (gitignored)
│   ├── ipo_seen.json
│   └── benchmark_scores.json
├── HW2_Tutorial.md                # Assignment write-up
├── requirements.txt
└── .gitignore
```

---

## Benchmark Results (Feb 22, 2026)

Scored with GPT-4o-mini on 5 dimensions (Completeness, Data Quality, Relevance, Clarity, Error-Free), each 1–5.

| Agent | Overall | Notes |
|-------|---------|-------|
| Bond Yield | 🟢 5.0 | Perfect score |
| Daily News | 🟢 4.8 | Relevance 4/5 |
| Earnings Reminder | 🟢 5.0 | Perfect score |
| IPO Scout | 🟡 3.8 | No tech IPOs on calendar — correct behavior, rubric penalizes empty table |
| Price Alerts | 🟢 5.0 | Perfect score |

Run `/benchmark` in Claude Code to re-score at any time.

---

## Tech Stack

| Layer | Tool | Cost |
|-------|------|------|
| Market data | yfinance (Yahoo Finance) | Free |
| News summarization | Groq llama-3.1-8b-instant | Free tier |
| Benchmark scoring | OpenAI GPT-4o-mini | ~$0.001/run |
| Email delivery | Gmail SMTP | Free |
| Scheduling | Windows Task Scheduler | Free |
| Agent interface | Claude Code skills | Free |
