# Investment Intelligence Daily Briefing System
### A Personal Agentic Workflow for Stock Market Monitoring
**MSIS — Agentic AI Assignment (HW2) · Nancy Huai · February 2026**

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [System Design Overview](#2-system-design-overview)
3. [Tech Stack](#3-tech-stack)
4. [Skill Documentation (Path A)](#4-skill-documentation-path-a)
5. [Building Process](#5-building-process)
6. [Real Usage + Iteration](#6-real-usage--iteration)
7. [Benchmark Methodology and Findings](#7-benchmark-methodology-and-findings)
8. [Reflection](#8-reflection)
9. [Appendix A — Benchmark Scorecard](#appendix-a--benchmark-scorecard)
10. [Appendix B — Prompt Listing](#appendix-b--prompt-listing)

---

## 1. Problem Statement

### The Pain Point

I personally hold positions in two specific stocks — **ALAB (Astera Labs)** and **IT (Gartner)** — and follow a broader watchlist of ~13 growth and tech names. Every morning before the US market opens I used to:

1. Open Yahoo Finance and check prices for each ticker manually (~8 minutes)
2. Google for earnings announcements for the next week (~5 minutes)
3. Skim financial news headlines to gauge market mood (~10 minutes)
4. Check the IPO calendar for upcoming tech IPOs (~5 minutes)

Total: **25–30 minutes of repetitive information gathering** before I could even think about any investment decisions.

The problems with this status quo:
- **Inconsistency** — some days I skipped steps when rushed
- **No alerts** — I had to remember to check, rather than being notified when something crossed a threshold
- **No synthesis** — raw data with no actionable framing
- **Zero scalability** — adding more tickers made it worse linearly

### Why an Agentic Workflow

An agentic system is ideal here because the task is:
- **Repetitive and well-defined** — the same data sources, the same format, every day
- **Time-sensitive** — must run before market open
- **Multi-source** — five independent data feeds that need to be collected and combined
- **Evaluable** — there is a clear rubric for what "good output" looks like (accurate prices, real dates, a 3-item summary under 200 words)

The alternative — a single ChatGPT prompt — cannot fetch live data, cannot remember which IPOs it already flagged, and cannot send an email.

### What the System Does

Six specialized agents collect data from different sources, their outputs are assembled by an orchestrator into a single formatted email, and the email is delivered to the user at 8:00 AM Pacific every weekday via Gmail SMTP. On demand, a seventh component runs an LLM-as-judge benchmark to score the quality of every agent.

---

## 2. System Design Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     DAILY REPORT ORCHESTRATOR                   │
│                      (daily_report.py)                          │
│                    Runs at 8:00 AM Pacific                      │
│                   via Windows Task Scheduler                    │
└────────┬────────────────────────────────────────────────────────┘
         │  imports and calls each agent's build_*_section()
         │
    ┌────▼─────┐  ┌──────────▼──┐  ┌────────▼──────┐
    │  Daily   │  │  Bond Yield  │  │   Earnings    │
    │  News    │  │   Agent      │  │   Reminder    │
    │  Agent   │  │  (yfinance)  │  │   Agent       │
    │ (Groq    │  └─────────────┘  │  (yfinance)   │
    │ LLaMA)   │                    └───────────────┘
    └──────────┘
    ┌──────────┐  ┌─────────────┐  ┌───────────────┐
    │  Price   │  │ Stock News  │  │   IPO Scout   │
    │  Alerts  │  │  Summary    │  │   Agent       │
    │  Agent   │  │(ALAB & IT)  │  │ (web scrape)  │
    │(yfinance)│  │  (Groq)     │  └───────────────┘
    └──────────┘  └─────────────┘
         │
    ┌────▼────────────────────────────────────────────┐
    │           Gmail SMTP Delivery                   │
    │    (HTML + plain text, sent to self)            │
    └─────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────┐
    │         BENCHMARK SYSTEM (on-demand)             │
    │            (benchmark.py + /benchmark)           │
    │  Runs all 6 agents → scores with GPT-4o-mini    │
    │  Saves results to state/benchmark_scores.json   │
    │  Last scores included in next daily email        │
    └──────────────────────────────────────────────────┘
```

### Agent Roles

| # | Agent | File | Data Source | Purpose |
|---|-------|------|-------------|---------|
| 1 | Daily News | `daily_news.py` | yfinance + Groq | Top 3 market-moving headlines, ≤200 words |
| 2 | Bond Yield | `bond_yield.py` | yfinance (^TNX) | 10-year Treasury yield, daily Δ, investor context |
| 3 | Earnings Reminder | `earnings_reminder.py` | yfinance calendar | Alert if watchlist stock earns in ≤2 days |
| 4 | Price Alerts | `price_alerts.py` | yfinance | Alert if price crosses configured threshold |
| 5 | IPO Scout | `ipo_scout.py` | stockanalysis.com | Upcoming tech IPOs, ⭐ flags new ones |
| 6 | Stock News Summary | `stock_summary.py` | yfinance + Groq | ≤3 impactful bullets for ALAB and IT with direction signs |
| 7 | Benchmark | `benchmark.py` | subprocess + GPT-4o-mini | LLM-as-judge quality scores for all agents |

### File Structure

```
investment-agents/
├── agents/
│   ├── bond_yield.py
│   ├── daily_news.py
│   ├── earnings_reminder.py
│   ├── ipo_scout.py
│   ├── price_alerts.py
│   ├── stock_summary.py
│   ├── daily_report.py        ← orchestrator + email sender
│   └── benchmark.py           ← LLM-as-judge scorer
├── config/
│   ├── email_config.json      ← SMTP creds + API keys
│   ├── watchlist.json         ← tickers for earnings alerts
│   ├── thresholds.json        ← price alert levels
│   └── ipo_config.json        ← tech keywords for IPO filter
├── state/
│   ├── ipo_seen.json          ← tracks previously seen IPOs
│   └── benchmark_scores.json  ← saved benchmark results
└── requirements.txt
```

### Skills in Claude Code

Each agent is also accessible as an on-demand Claude Code skill:

```
~/.claude/skills/
├── bond-yield/SKILL.md
├── daily-news/SKILL.md
├── earnings-reminder/SKILL.md
├── ipo-scout/SKILL.md
├── price-alerts/SKILL.md
├── stock-summary/SKILL.md
└── benchmark/SKILL.md
```

Typing `/bond-yield` in Claude Code runs the bond yield agent and formats the result. Typing `/benchmark` runs all agents, scores them, and presents a color-coded scorecard.

---

## 3. Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| Language | Python 3.11 | Free |
| Market data | yfinance (Yahoo Finance) | Free |
| Web scraping | BeautifulSoup4 + requests | Free |
| LLM for news summary | Groq (llama-3.1-8b-instant) | Free tier |
| LLM for benchmark scoring | OpenAI GPT-4o-mini | ~$0.001/run |
| Email delivery | Gmail SMTP with App Password | Free |
| Scheduling | Windows Task Scheduler | Free (built-in) |
| Agent interface | Claude Code skills (SKILL.md) | Free |

**Total ongoing cost: ~$0.005/day** (one OpenAI benchmark call, otherwise entirely free APIs)

---

## 4. Skill Documentation (Path A)

### 4.1 Skill: Bond Yield Agent

**Purpose:** Fetch the US 10-year Treasury yield (^TNX) and provide investor context.

**Inputs:** None (pulls live data automatically)

**Outputs:**
- Current yield percentage
- Daily change in basis points (bps) with direction arrow (▲/▼)
- Context sentence explaining what the yield level means

**Logic:** No LLM involved — pure rule-based context using threshold brackets:

```python
def yield_context(y: float) -> str:
    if y < 2.5:   return 'Very low — historically accommodative, supportive of equities'
    elif y < 3.5: return 'Low-moderate — broadly supportive for growth stocks'
    elif y < 4.0: return 'Moderate — neutral; watch for direction'
    elif y < 4.5: return 'Elevated — pressure on valuations, especially high-growth names'
    elif y < 5.0: return 'High — restrictive; watch rate-sensitive sectors (tech, real estate)'
    else:         return 'Very high — significant headwind for growth stocks; recession risk watch'
```

**Sample output (Feb 22, 2026):**
```
════════════════════════════════════════════════════════════
  📈  10-YEAR TREASURY YIELD
  Sunday, February 22 2026  15:23
════════════════════════════════════════════════════════════

  Current Yield : 4.086%
  Daily Change  : ▲ +1.1 bps  (+0.011%)
  Context       : Elevated — pressure on valuations, especially high-growth names
```

---

### 4.2 Skill: Daily News Agent

**Purpose:** Pull recent headlines from 10 major market tickers, use Groq to select and summarize the 3 most market-moving items in ≤200 words.

**Inputs:** None (fetches automatically from SPY, QQQ, AAPL, MSFT, NVDA, META, TSLA, AMZN, GOOGL, DIA)

**Outputs:**
- 3 numbered news items with bold topic and 1–2 sentences of market context
- Market Mood indicator (🟢 Bullish / 🔴 Bearish / 🟡 Mixed)

**Prompt (sent to Groq llama-3.1-8b-instant):**
```
You are a concise financial news editor.
From the headlines below, select the 3 items most likely to move markets today.
Write a numbered summary in 200 words or less total.
Each item: bold the company/topic, then 1-2 sentences on why it matters for investors.
No fluff, no intro sentence, go straight to item 1.

[headlines list]
```

**Key design decisions:**
- "No intro sentence, go straight to item 1" — eliminated Groq's tendency to write a preamble
- `temperature: 0.3` — low temperature keeps the summary factual, not creative
- `max_tokens: 350` — sufficient for 200-word summary with some buffer

---

### 4.3 Skill: Earnings Reminder Agent

**Purpose:** Check every ticker on the watchlist for upcoming earnings; trigger an alert (T-2) if any report within 2 days.

**Inputs:** `config/watchlist.json` — currently 13 tickers: `["AMZN", "MSFT", "NVDA", "HOOD", "TSM", "RIVN", "IT", "TSLA", "SMCI", "AMD", "ALAB", "VRTX", "CRM"]`

**Outputs:**
- 🚨 Alert section (earnings in 0–2 days)
- 📆 Upcoming table (earnings in 3–30 days): Ticker, Company, Date, Days Away
- ⚠️ Warning if any ticker failed to fetch

**No LLM involved** — purely yfinance calendar data.

**Sample output (Feb 22, 2026):**
```
  ✅  No earnings in the next 2 days for your watchlist.

  📆  Upcoming earnings (next 30 days):

    NVDA      NVIDIA Corporation          2026-02-25  (in 3 days)
    CRM       Salesforce, Inc.            2026-02-25  (in 3 days)
```

---

### 4.4 Skill: Price Alerts Agent

**Purpose:** Compare current prices against configured upper/lower thresholds; alert on breaches.

**Inputs:** `config/thresholds.json`
```json
{
  "AAPL":  { "above": 240, "below": 180 },
  "NVDA":  { "above": 160, "below": 100 },
  "MSFT":  { "above": 460, "below": 370 },
  "ALAB":  { "above": 180, "below": null },
  "IT":    { "above": 200, "below": null }
}
```

**Outputs:**
- 🚨 Triggered alerts with price, threshold, and % distance
- 📊 Within-range table for all non-triggered tickers

**No LLM** — pure arithmetic comparison.

**Sample output (Feb 22, 2026):**
```
  🚨  4 THRESHOLD(S) BREACHED:

    📈  AAPL      $264.58  ABOVE ↑ $240  (+10.2% from threshold)
    📈  NVDA      $189.82  ABOVE ↑ $160  (+18.6% from threshold)
    📈  GOOGL     $314.98  ABOVE ↑ $210  (+50.0% from threshold)
    📈  TSLA      $411.82  ABOVE ↑ $400  (+3.0% from threshold)

  📊  Within range:
    MSFT      $ 397.23      $370      $460
    META      $ 655.66      $520      $700
    ALAB      $ 129.68         —      $180
    IT        $ 153.73         —      $200
```

---

### 4.5 Skill: IPO Scout Agent

**Purpose:** Scrape `stockanalysis.com` for upcoming IPOs, filter to tech sector using keyword matching, and flag new ones with ⭐ that weren't present in the last run.

**Inputs:** `config/ipo_config.json` (tech keyword list), `state/ipo_seen.json` (persistence)

**Key tech keywords (subset):** `['tech', 'software', 'ai', 'artificial intelligence', 'data', 'cloud', 'cyber', 'saas', 'semiconductor', 'fintech', 'digital']`

**State management:** The agent writes newly-seen IPO symbols to `ipo_seen.json` after each run. On the next run it compares against this set — any new symbol gets a ⭐.

**Failure mode (graceful):** When no tech IPOs are scheduled (as on Feb 22, 2026), the agent prints "No upcoming tech IPOs found at this time." — this is correct behavior, not an error.

---

### 4.6 Skill: Stock News Summary Agent

**Purpose:** Fetch public news for ALAB (Astera Labs) and IT (Gartner), use Groq to identify the ≤3 most impactful items per ticker, and annotate each with a direction sign (📈/📉) and a clickable source link. Skip silently if nothing is impactful.

**Inputs:** None (fetches via yfinance news API, up to 10 articles per ticker)

**Prompt (sent to Groq):**
```
You are a stock analyst. Write bullet-point summaries for ALAB and IT.

FORMAT — each bullet must look exactly like these examples:
- UP ALAB **Price Target Raised** — BofA raised target to $200, boosting sentiment [ref:2]
- DOWN IT **Earnings Miss** — Weak Q4 EPS may pressure stock lower [ref:11]

RULES:
- UP = price likely rises, DOWN = price likely falls
- Bold only the short topic using **double asterisks**
- End each bullet with [ref:N] — the headline number
- Max 3 bullets for ALAB, max 3 for IT — no duplicates
- Skip a ticker entirely if its headlines are not impactful
- If NEITHER ticker has impactful news, output only: NO_IMPACT
- No numbered lists, no section headers, no extra text

=== ALAB (Astera Labs) headlines ===
[1] Title — summary snippet...
...

=== IT (Gartner) headlines ===
[6] Title — summary snippet...
...
```

**Sample output (Feb 22, 2026):**
```
  📈 ALAB Price Target Raised — BofA raised target to $200, boosting sentiment
     https://finance.yahoo.com/news/bofa-raises-price-target-astera-111005827.html

  📈 ALAB Positive Sentiment — Among 12 Best Tech Stocks that Beat Earnings Estimates
     https://finance.yahoo.com/news/...
```

**Prompt iteration history (see Section 6 for full details):**
- **V1:** Single flat list of all articles → Groq processed ALAB headlines and stopped before IT
- **V2:** Two explicit sections (`=== ALAB headlines ===` / `=== IT headlines ===`) → both tickers processed
- **V3 (current):** Added exact bullet-format examples → direction sign and `[ref:N]` format followed consistently

---

### 4.7 Skill: Benchmark (LLM-as-Judge)

**Purpose:** Run all 5 core agents via subprocess, capture their stdout, score each output with GPT-4o-mini on 5 rubric dimensions, print a terminal scorecard, and save results for inclusion in the next daily email.

**Invocation:** `python agents/benchmark.py` or `/benchmark` in Claude Code

**Scoring prompt (sent to GPT-4o-mini):**
```
You are an LLM-as-judge evaluating the output of an automated investment data agent.

## Agent Description
{rubric for this specific agent}

## Agent Output to Evaluate
{agent's stdout, up to 3000 characters}

## Scoring Task
Score this output on exactly 5 dimensions, each from 1 to 5:
- completeness  (1=missing key fields, 5=all expected fields present)
- data_quality  (1=wrong/invalid values or format, 5=values in expected ranges/format)
- relevance     (1=not actionable for investor, 5=clearly actionable insights)
- clarity       (1=hard to parse/poorly structured, 5=well-structured and readable)
- error_free    (1=exceptions/failures/fallback messages present, 5=clean successful run)

Respond with ONLY valid JSON — no markdown, no explanation, no code fences:
{"scores": {"completeness": N, "data_quality": N, "relevance": N, "clarity": N, "error_free": N}, "summary": "one sentence max 20 words"}
```

**Design notes:**
- Short-circuits to all-1s if the agent itself crashed (no API call wasted)
- Strips accidental markdown fences from GPT response before `json.loads()`
- Uses `sys.executable` to ensure subprocess agents run in the same Python environment
- Results saved as timestamped list to `state/benchmark_scores.json`

---

## 5. Building Process

### Tools Used
- **Claude Code (Sonnet 4.6)** — all code written, debugged, and iterated via conversation
- **Python 3.11** on Windows 11
- **yfinance** — free, no API key needed for market data
- **Groq free tier** — llama-3.1-8b-instant, ~150 req/day free limit
- **OpenAI GPT-4o-mini** — benchmark scoring only (~$0.001 per full benchmark run)
- **Gmail App Password** — for email delivery without OAuth complexity

### Build Sequence

**Step 1 — Core agents (1–2 hours)**
The five agents were built individually as standalone Python scripts. Each follows the same pattern: fetch data → format output → print to stdout. The stdout-first design was intentional: it makes each agent testable in isolation and allows the benchmark to capture output via `subprocess.run(capture_output=True)`.

**Step 2 — Config files (30 min)**
Created `watchlist.json`, `thresholds.json`, `email_config.json`, and `ipo_config.json`. All user-editable parameters are in JSON files rather than hardcoded — this allows changing the watchlist or thresholds without touching Python.

**Step 3 — Skills (30 min)**
For each agent, created a `SKILL.md` in `~/.claude/skills/`. This enables on-demand invocation from Claude Code via `/bond-yield`, `/earnings-reminder`, etc.

**Step 4 — Orchestrator + email (1 hour)**
`daily_report.py` imports each agent's section builder and assembles HTML + plain-text email. The HTML uses inline styles (required by Gmail) with color-coded section headers.

**Step 5 — Task Scheduler (30 min)**
Configured Windows Task Scheduler to run `daily_report.py` at 8:00 AM Pacific daily. The machine's timezone is confirmed as Pacific Standard Time. The Python executable path was set to the same interpreter used for development (`sys.executable`).

**Step 6 — Stock News Summary (2 hours, with iteration)**
This was the most complex agent due to the LLM interaction. See Section 6 for the full iteration log.

**Step 7 — Benchmark system (1 hour)**
Built `benchmark.py` using `subprocess.run` to capture each agent's stdout, then OpenAI GPT-4o-mini as judge. The `run_benchmark()` function is importable so `daily_report.py` can display the last saved scores in the email without re-running all agents.

### Frustrating Parts

1. **yfinance API schema change** — yfinance news changed from a flat dict (`item['title']`) to a nested structure (`item['content']['title']`). Fixed by falling back: `content = item.get('content', item)`.

2. **Gmail SMTP "Less Secure App" deprecation** — Gmail now requires App Passwords (not account password). Required enabling 2FA first, then generating an App Password in Google Account settings.

3. **Groq stopping mid-output** — When given 20 articles in a flat list, Groq would process the first 5 (all ALAB) and stop. The model was completing what it considered a "natural" response end. Fixed with a two-section prompt structure.

4. **IT ticker matching substring** — Ticker "IT" appeared in words like "MARKET" and "DIGITAL". Fixed with `re.search(r'\bIT\b', b)` (word boundary regex).

5. **API provider switch** — Initially designed benchmark to use Anthropic Claude Haiku. Switched to OpenAI GPT-4o-mini when Anthropic balance was insufficient. This required changing the client library, response parsing, and key name.

---

## 6. Real Usage + Iteration

### Run 1 — First Full Email Test

**Input:** System invoked for the first time to send a live test email.

**Result received:**
- ✅ Bond Yield section: correct, clean
- ✅ Earnings Reminder: correct (no imminent earnings)
- ✅ Price Alerts: 4 breaches found correctly
- ✅ IPO Scout: "No upcoming tech IPOs" — correct for the date
- ❌ Daily News: **Groq API key not found** — agent was looking for `GROQ_API_KEY` environment variable, not `email_config.json`
- ❌ Stock News Summary (ALAB/Gartner): Multiple issues:
  1. **Duplicate bullets** — Groq repeated the same topic (e.g., "Strong Insider Ownership") twice
  2. **No direction signs** — 📈/📉 icons not appearing; regex `\[(UP|DOWN)\]` failed because Groq output `UP` without brackets
  3. **Links not visible** — `text-decoration:none` CSS made links invisible

**Changes made after Run 1:**

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Groq key not found in daily_news.py | Hard-coded to `os.environ.get('GROQ_API_KEY')` | Added `_load_groq_key()` reading from `email_config.json` |
| Duplicate bullets | Groq repeated same semantic topic | Added `seen_topics` set deduplification on bold topic text |
| Direction signs missing | Regex `\[(UP|DOWN)\]` required brackets | Changed to `\[?(UP|DOWN)\]?` (brackets optional) |
| Links invisible | CSS `text-decoration:none` hid hyperlinks | Changed to `text-decoration:underline` |

### Run 2 — After Fixes + Iteration

**Input:** Second live email test.

**Result received:**
- ✅ Daily News: working, 3 items, Market Mood indicator present
- ⚠️ Stock News Summary: ALAB bullets now correct (2 bullets, 📈 icon, clickable links), but **only 1 bullet showing for IT** — investigation revealed Groq stopping after ALAB articles when max_tokens=400 caused response truncation

**Changes made after Run 2:**

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Only ALAB bullets, no IT | Groq's full response cut off at 400 tokens | Increased `max_tokens` from 400 to 600 |
| IT bullets missing entirely | Flat 20-article list — Groq processed ALAB first and "finished" | Restructured prompt into two explicit sections with `=== ALAB headlines ===` and `=== IT headlines ===` |
| `- NO_IMPACT` lines appearing as bullets | Groq emitting `NO_IMPACT` as content line rather than only as sole output | Added filter: `if 'NO_IMPACT' not in l.upper()` |

**After Run 2 the user confirmed:** "Looks good."

### Prompt Critique

**Daily News prompt — strengths:**
- Role specification ("You are a concise financial news editor") anchors the tone
- Hard word limit (200 words) enforces brevity
- "No fluff, no intro sentence" prevents common LLM padding behavior

**Daily News prompt — weaknesses:**
- No instruction on what to do when news is redundant (e.g., three NVDA articles)
- "Most likely to move markets" is subjective — the model may not prioritize the same items a human analyst would

**Stock Summary prompt — strengths:**
- Exact format examples with both UP and DOWN cases remove ambiguity
- Two-section structure prevents the model from prematurely finishing
- `NO_IMPACT` escape clause handles the "no news today" case gracefully

**Stock Summary prompt — weaknesses:**
- `[ref:N]` format requires the model to remember the article numbers, which occasionally causes mis-references
- The prompt cannot specify that both `ALAB` and `IT` must appear in separate bullets if both have news — it only says "max 3 per ticker"

---

## 7. Benchmark Methodology and Findings

### Design Rationale

I chose **LLM-as-judge** (method 2 from Appendix 2) for the following reasons:

1. **Speed** — all 5 agents can be scored in under 60 seconds
2. **Repeatability** — the same rubric is applied identically each run
3. **No human availability required** — I can run this before market open without waiting for manual review
4. **Regression detection** — if a data source changes its format, the score will drop on the next run

### Rubric Dimensions

Each agent is scored on 5 dimensions, each 1–5, with the overall score being the average:

| Dimension | Score 1 | Score 5 |
|-----------|---------|---------|
| **Completeness** | Missing key expected fields | All expected fields present |
| **Data Quality** | Wrong/invalid values or format | Values in expected ranges and format |
| **Relevance** | Not actionable for an investor | Clearly actionable insights |
| **Clarity** | Hard to parse or poorly structured | Well-structured and readable |
| **Error-Free** | Exceptions, crashes, or fallback messages | Clean, successful run |

### Frozen Settings

To ensure reproducibility across benchmark runs:
- All agent scripts are unchanged between runs
- GPT-4o-mini `model='gpt-4o-mini'` and `max_tokens=256` are fixed in `benchmark.py`
- Each agent is scored on its actual stdout output, truncated to 3,000 characters if longer
- The benchmark prompt is stored verbatim in `benchmark.py` (no dynamic modification)

### Test Cases

**Test Case 1 — Standard Run (Feb 22, 2026, 3:18 PM Pacific)**

Conditions: US markets closed for Sunday. Data reflects Friday's close.

| Agent | Overall | Compl. | Quality | Relev. | Clarity | No-Err | Judge Summary |
|-------|---------|--------|---------|--------|---------|--------|---------------|
| Bond Yield | 🟢 5.0 | 5 | 5 | 5 | 5 | 5 | "All required fields present, values are valid, and insights are clear and actionable." |
| Daily News | 🟢 4.8 | 5 | 5 | 4 | 5 | 5 | "The output successfully summarizes key market news with clear indicators and structure." |
| Earnings Reminder | 🟢 5.0 | 5 | 5 | 5 | 5 | 5 | "The output is complete, clear, and actionable without any errors." |
| IPO Scout | 🟡 3.8 | 1 | 5 | 3 | 5 | 5 | "Output clearly states no upcoming tech IPOs are found." |
| Price Alerts | 🟢 5.0 | 5 | 5 | 5 | 5 | 5 | "Output meets all criteria with clear actionable insights and no errors." |

**Test Case 2 — Edge Case: No IPOs Available**

IPO Scout returned "No upcoming tech IPOs found at this time." This is an intentional edge case — there are genuinely no upcoming tech IPOs on the calendar for this period.

**Analysis:** The judge correctly penalized **Completeness = 1** because the rubric expects a table with Symbol/Company/Date columns. However, the agent is behaving correctly — the data simply is not available. This reveals a limitation of pure LLM-as-judge scoring: the judge evaluates output against an ideal template, but does not know whether the absence of data is a code failure or a real-world condition.

**Failure Mode:** The IPO Scout score of 3.8 will automatically recover to ≥4.5 the next time real tech IPOs are listed. This is a **data availability issue, not a code defect**.

### Edge Case: What Happens When an Agent Crashes?

The benchmark includes a short-circuit: if `subprocess.run()` returns a non-zero exit code, or if the stdout starts with `[` (the error prefix format), the agent is automatically assigned all-1s without spending an OpenAI API call. This prevents runaway costs if an upstream API is down.

### Baseline Comparison

**Baseline:** Manual daily monitoring (the pre-system workflow described in Section 1)

| Metric | Manual Workflow | Agentic System |
|--------|----------------|----------------|
| Time to collect all data | 25–30 min | 0 min (automated) |
| Consistency | Variable (skipped when rushed) | 100% (Task Scheduler) |
| Earnings alert lead time | 0 (checked on the day) | 2 days ahead |
| Price breach detection | Noticed when checking manually | Immediate on email |
| Coverage (tickers) | ~5 tickers casually | 13 watchlist + 8 alert tickers |
| Cost | 0 (time only) | ~$0.005/day |

### Aggregate Results

- **4 out of 5 agents scored 🟢 ≥ 4.0** on the first benchmark run
- **Mean overall score: 4.72 / 5.0**
- **One agent flagged (IPO Scout, 3.8)** — data availability issue, not a code failure
- **Zero agents crashed** — error_free = 5 across all agents
- **Lowest individual dimension score: Completeness = 1 (IPO Scout)** — expected when no IPOs are available

---

## 8. Reflection

### Why This Workflow

I chose this workflow because it addresses a daily habit that genuinely costs time and attention. The data collection is mechanical — there is no judgment involved in fetching a yield or checking a price. Automating the mechanical parts frees up cognitive bandwidth for the actual decisions (should I buy/sell/hold?), which an AI cannot make for me.

### What Worked Well

1. **yfinance as the backbone** — free, reliable, no rate limits for the data volumes involved. Handles stocks, ETFs, and Treasury instruments uniformly.

2. **Section-based architecture** — having each agent as an independent script with its own `main()` and a separate `build_*_section()` for the email meant I could test agents individually before integrating them. When the email looked wrong, I could immediately isolate which agent was the source.

3. **Plain-text + HTML dual output** — sending both formats ensures the email is readable in any email client, including mobile.

4. **LLM-as-judge benchmark** — running the benchmark after every significant code change takes under 60 seconds and immediately shows whether a fix improved or regressed any agent. This is much faster than reading a full email and manually assessing every section.

### What Did Not Work

1. **Groq's output format compliance** — even with explicit format examples, Groq occasionally deviates: emitting `NO_IMPACT` as an embedded line, adding section headers, or varying whether direction labels have brackets. Each deviation required a parsing fix in Python code (stripping, filtering, flexible regex). The more reliable approach would be to use a function-calling API that enforces structured JSON output, but Groq's free tier does not support this as reliably.

2. **IPO Scout data dependency** — the score drops to 3.8 when no IPOs are available. The agent is correct, but the benchmark cannot distinguish "no data" from "broken agent." A future improvement would add an explicit "no data available" status to the rubric.

3. **Single point of failure for email** — if Gmail SMTP is blocked (e.g., network issue), the entire orchestrator fails silently. No retry logic or fallback delivery exists yet.

### How Prompts Evolved

The most-iterated prompt was the Stock News Summary. Three key changes:

| Version | Change | Effect |
|---------|--------|--------|
| V1 | Single flat list of 20 articles | Groq processed ALAB only and stopped |
| V2 | Two sections (`=== ALAB ===` / `=== IT ===`) | Both tickers processed |
| V3 | Added exact format examples with UP/DOWN cases | `[ref:N]` format followed, direction signs appeared |

The key lesson: **examples are more effective than rules for format compliance**. Telling the model "end each bullet with [ref:N]" was less effective than showing it exactly what a bullet should look like.

### Would I Keep Using This System?

Yes, already using it. The daily email arrived on schedule during testing and contained all the information I previously gathered manually in a fraction of the time. The two most immediately valuable sections are **Earnings Reminder** (the 2-day T-2 alert prevents being caught off-guard by earnings volatility) and **Price Alerts** (four tickers currently above my thresholds — information I would have missed on a busy day).

The one change I would make next: add a "position summary" section that shows my actual P&L for ALAB and IT based on my entry prices, so the daily email also functions as a portfolio snapshot rather than just a market data feed.

---

## Appendix A — Benchmark Scorecard

**Run timestamp:** 2026-02-22T15:18:20
**Scorer:** GPT-4o-mini (`gpt-4o-mini`, `max_tokens=256`, `temperature=1.0` default)
**Saved to:** `state/benchmark_scores.json`

### Full Scores Table

| Agent | Completeness | Data Quality | Relevance | Clarity | Error-Free | **Overall** |
|-------|-------------|-------------|-----------|---------|-----------|-------------|
| Bond Yield | 5 | 5 | 5 | 5 | 5 | **5.0 🟢** |
| Daily News | 5 | 5 | 4 | 5 | 5 | **4.8 🟢** |
| Earnings Reminder | 5 | 5 | 5 | 5 | 5 | **5.0 🟢** |
| IPO Scout | 1 | 5 | 3 | 5 | 5 | **3.8 🟡** |
| Price Alerts | 5 | 5 | 5 | 5 | 5 | **5.0 🟢** |

**Mean overall: 4.72 / 5.0**

### Judge Summaries (verbatim from GPT-4o-mini)

- **Bond Yield:** "All required fields present, values are valid, and insights are clear and actionable."
- **Daily News:** "The output successfully summarizes key market news with clear indicators and structure."
- **Earnings Reminder:** "The output is complete, clear, and actionable without any errors."
- **IPO Scout:** "Output clearly states no upcoming tech IPOs are found."
- **Price Alerts:** "Output meets all criteria with clear actionable insights and no errors."

### IPO Scout Failure Analysis

IPO Scout received Completeness = 1 because the judge's rubric expects "a formatted table with Symbol, Company, Date columns." On this date, the agent returned:

```
  No upcoming tech IPOs found at this time.
```

This is **correct agent behavior** — stockanalysis.com genuinely showed no upcoming tech IPOs on Feb 22, 2026. The rubric mismatch indicates a limitation of template-based LLM scoring: the judge cannot distinguish between a missing table (bug) and a legitimately empty result (expected behavior). A more robust rubric would add: *"If no tech IPOs are found, a clear 'no results' message is acceptable and completeness should be scored 3 or higher."* (This edge case handling has since been added to the IPO Scout rubric in `benchmark.py`.)

---

## Appendix B — Prompt Listing

### B.1 Daily News — Groq Prompt

```
You are a concise financial news editor.
From the headlines below, select the 3 items most likely to move markets today.
Write a numbered summary in 200 words or less total.
Each item: bold the company/topic, then 1-2 sentences on why it matters for investors.
No fluff, no intro sentence, go straight to item 1.

{headlines list — title + publisher + first 300 chars of summary}
```

Model: `llama-3.1-8b-instant` | Temperature: 0.3 | Max tokens: 350

### B.2 Stock News Summary — Groq Prompt (V3, current)

```
You are a stock analyst. Write bullet-point summaries for ALAB and IT.

FORMAT — each bullet must look exactly like these examples:
- UP ALAB **Price Target Raised** — BofA raised target to $200, boosting sentiment [ref:2]
- DOWN IT **Earnings Miss** — Weak Q4 EPS may pressure stock lower [ref:11]

RULES:
- UP = price likely rises, DOWN = price likely falls
- Bold only the short topic using **double asterisks**
- End each bullet with [ref:N] — the headline number
- Max 3 bullets for ALAB, max 3 for IT — no duplicates
- Skip a ticker entirely if its headlines are not impactful
- If NEITHER ticker has impactful news, output only: NO_IMPACT
- No numbered lists, no section headers, no extra text

=== ALAB (Astera Labs) headlines ===
[N] Title — summary snippet...

=== IT (Gartner) headlines ===
[N] Title — summary snippet...
```

Model: `llama-3.1-8b-instant` | Temperature: 0.3 | Max tokens: 600

### B.3 Benchmark — GPT-4o-mini Scoring Prompt

```
You are an LLM-as-judge evaluating the output of an automated investment data agent.

## Agent Description
{per-agent rubric}

## Agent Output to Evaluate
{stdout, up to 3000 chars}

## Scoring Task
Score this output on exactly 5 dimensions, each from 1 to 5:
- completeness  (1=missing key fields, 5=all expected fields present)
- data_quality  (1=wrong/invalid values or format, 5=values in expected ranges/format)
- relevance     (1=not actionable for investor, 5=clearly actionable insights)
- clarity       (1=hard to parse/poorly structured, 5=well-structured and readable)
- error_free    (1=exceptions/failures/fallback messages present, 5=clean successful run)

Respond with ONLY valid JSON — no markdown, no explanation, no code fences:
{"scores": {"completeness": N, "data_quality": N, "relevance": N, "clarity": N, "error_free": N}, "summary": "one sentence max 20 words"}
```

Model: `gpt-4o-mini` | Max tokens: 256

---

*System artifact:* `C:\Users\nancy\investment-agents\` — all source files, config, and state
*Skills:* `C:\Users\nancy\.claude\skills\` — 7 SKILL.md files for Claude Code
*Benchmark results:* `state/benchmark_scores.json`
*Generated:* February 22, 2026
