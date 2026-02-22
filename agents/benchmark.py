"""
Agent Benchmark — LLM-as-Judge scoring for all 5 investment agents.

Runs each agent via subprocess, scores the captured output using
Claude Haiku on 5 rubric dimensions (1-5 each), saves results to
state/benchmark_scores.json, and prints a terminal report.

Usage:
    python ~/investment-agents/agents/benchmark.py

Config:
    anthropic_api_key in ~/investment-agents/config/email_config.json
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
import subprocess
from datetime import datetime
from pathlib import Path

import openai

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE        = Path.home() / 'investment-agents'
AGENTS_DIR  = BASE / 'agents'
CONFIG_DIR  = BASE / 'config'
STATE_DIR   = BASE / 'state'
EMAIL_CFG   = CONFIG_DIR / 'email_config.json'
SCORES_FILE = STATE_DIR  / 'benchmark_scores.json'
PYTHON_EXE  = sys.executable

# ── Agent registry ────────────────────────────────────────────────────────────
AGENTS = [
    {
        'key':    'bond_yield',
        'label':  'Bond Yield',
        'script': AGENTS_DIR / 'bond_yield.py',
        'rubric': (
            "This agent monitors the US 10-year Treasury yield (^TNX). "
            "A good output contains: (1) a current yield percentage (e.g. '4.523%'), "
            "(2) a daily change in basis points (e.g. '+2.1 bps'), "
            "(3) a direction arrow (▲ or ▼ or ─), and (4) a context sentence explaining "
            "what the yield level means for investors (e.g. 'Elevated — pressure on "
            "valuations...'). Output should have no Python errors or tracebacks."
        ),
    },
    {
        'key':    'daily_news',
        'label':  'Daily News',
        'script': AGENTS_DIR / 'daily_news.py',
        'rubric': (
            "This agent summarizes the 3 most market-moving news items of the day. "
            "A good output contains: (1) exactly 3 numbered news items, (2) each item "
            "has a bold topic and 1-2 sentences of market context, (3) a 'Market Mood' "
            "indicator (Bullish/Bearish/Mixed with emoji), and (4) total summary ≤200 words. "
            "Output should not contain API error messages or fallback text like 'key not found'."
        ),
    },
    {
        'key':    'earnings_reminder',
        'label':  'Earnings Reminder',
        'script': AGENTS_DIR / 'earnings_reminder.py',
        'rubric': (
            "This agent checks which watchlist stocks have earnings in the next 2 days "
            "and lists upcoming earnings in the next 30 days. A good output contains: "
            "(1) a clear T-2 alert section (alerts or confirmation of none), "
            "(2) an upcoming earnings table with ticker, company name, date, and days away, "
            "(3) the watchlist tickers checked (should be 10+), and "
            "(4) no Python errors or 'Could not fetch' for all tickers."
        ),
    },
    {
        'key':    'ipo_scout',
        'label':  'IPO Scout',
        'script': AGENTS_DIR / 'ipo_scout.py',
        'rubric': (
            "This agent scrapes for upcoming tech IPOs and flags new ones with ⭐. "
            "A good output contains: (1) a formatted table with Symbol, Company, Date columns, "
            "(2) ⭐ markers on IPOs not seen before, (3) a summary count line. "
            "If no tech IPOs are found, 'No upcoming tech IPOs found' is acceptable "
            "and should still score well on clarity and error-free dimensions."
        ),
    },
    {
        'key':    'price_alerts',
        'label':  'Price Alerts',
        'script': AGENTS_DIR / 'price_alerts.py',
        'rubric': (
            "This agent checks stock prices against configured thresholds. "
            "A good output contains: (1) a triggered alerts section or clear 'no breaches' message, "
            "(2) a 'Within range' table showing current price vs thresholds for each ticker, "
            "(3) prices formatted as '$NNN.NN', and (4) % distance from threshold for alerts. "
            "The within-range table must include at least 3 tickers."
        ),
    },
]

# ── Config ────────────────────────────────────────────────────────────────────
def load_openai_key() -> str:
    try:
        cfg = json.loads(EMAIL_CFG.read_text(encoding='utf-8'))
        return cfg.get('openai_api_key', '')
    except Exception:
        return ''

# ── Agent runner ──────────────────────────────────────────────────────────────
def run_agent(script_path: Path, timeout: int = 60) -> tuple[str, bool]:
    """Run agent via subprocess; returns (stdout, success)."""
    try:
        result = subprocess.run(
            [PYTHON_EXE, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace',
        )
        output = result.stdout
        if result.returncode != 0 and result.stderr:
            output += f'\n[stderr]: {result.stderr[:500]}'
        return output.strip() or '[No output produced]', result.returncode == 0
    except subprocess.TimeoutExpired:
        return f'[Agent timed out after {timeout}s]', False
    except Exception as e:
        return f'[Failed to run agent: {e}]', False

# ── Claude scorer ─────────────────────────────────────────────────────────────
SCORE_PROMPT = """\
You are an LLM-as-judge evaluating the output of an automated investment data agent.

## Agent Description
{rubric}

## Agent Output to Evaluate
```
{output}
```

## Scoring Task
Score this output on exactly 5 dimensions, each from 1 to 5:
- completeness  (1=missing key fields, 5=all expected fields present)
- data_quality  (1=wrong/invalid values or format, 5=values in expected ranges/format)
- relevance     (1=not actionable for investor, 5=clearly actionable insights)
- clarity       (1=hard to parse/poorly structured, 5=well-structured and readable)
- error_free    (1=exceptions/failures/fallback messages present, 5=clean successful run)

Respond with ONLY valid JSON — no markdown, no explanation, no code fences:
{{"scores": {{"completeness": N, "data_quality": N, "relevance": N, "clarity": N, "error_free": N}}, "summary": "one sentence max 20 words"}}
"""

DIMS = ['completeness', 'data_quality', 'relevance', 'clarity', 'error_free']

def score_output(client: openai.OpenAI, agent: dict, output: str, ran_ok: bool) -> dict:
    """Call GPT-4o-mini to score one agent output. Short-circuits to all-1s on failure."""
    if not ran_ok or output.startswith('['):
        return {
            'scores':  {d: 1 for d in DIMS},
            'overall': 1.0,
            'summary': 'Agent failed to run or produced no output.',
        }

    try:
        msg = client.chat.completions.create(
            model='gpt-4o-mini',
            max_tokens=256,
            messages=[{'role': 'user', 'content': SCORE_PROMPT.format(
                rubric=agent['rubric'],
                output=output[:3000],
            )}],
        )
        raw = msg.choices[0].message.content.strip()
        # Strip accidental markdown fences
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        parsed  = json.loads(raw.strip())
        scores  = parsed.get('scores', {})
        summary = parsed.get('summary', 'No summary.')
        for d in DIMS:
            scores[d] = max(1, min(5, int(scores.get(d, 3))))
        overall = round(sum(scores[d] for d in DIMS) / len(DIMS), 1)
        return {'scores': scores, 'overall': overall, 'summary': summary}
    except Exception as e:
        return {
            'scores':  {d: 1 for d in DIMS},
            'overall': 1.0,
            'summary': f'Scoring call failed: {e}',
        }

# ── State ─────────────────────────────────────────────────────────────────────
def load_scores() -> list:
    if SCORES_FILE.exists():
        try:
            return json.loads(SCORES_FILE.read_text(encoding='utf-8'))
        except Exception:
            return []
    return []

def save_scores(records: list):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SCORES_FILE.write_text(json.dumps(records, indent=2), encoding='utf-8')

# ── Core orchestrator (importable) ────────────────────────────────────────────
def run_benchmark() -> dict:
    """Run all agents, score outputs with Claude, return results dict."""
    api_key = load_openai_key()
    if not api_key:
        print("  [!] openai_api_key not found in config/email_config.json\n")
        return {}

    client  = openai.OpenAI(api_key=api_key)
    results = {}

    for agent in AGENTS:
        print(f"  {agent['label']:<22}", end=' ', flush=True)
        output, ran_ok = run_agent(agent['script'])
        print('✓ captured →', end=' ', flush=True)
        result = score_output(client, agent, output, ran_ok)
        results[agent['key']] = result
        overall = result['overall']
        star = '🟢' if overall >= 4.0 else ('🟡' if overall >= 3.0 else '🔴')
        print(f'{star} {overall:.1f}')

    return results

# ── Terminal report ───────────────────────────────────────────────────────────
def print_report(results: dict, timestamp: str):
    dim_labels = {'completeness': 'Compl.', 'data_quality': 'Quality',
                  'relevance': 'Relev.', 'clarity': 'Clarity', 'error_free': 'No-Err'}

    print(f"\n  {'Agent':<22}  {'Overall':>7}  " +
          "  ".join(f"{dim_labels[d]:>7}" for d in DIMS))
    print(f"  {'─'*22}  {'─'*7}  " + "  ".join('─'*7 for _ in DIMS))

    for agent in AGENTS:
        if agent['key'] not in results:
            continue
        res     = results[agent['key']]
        overall = res['overall']
        scores  = res['scores']
        star    = '🟢' if overall >= 4.0 else ('🟡' if overall >= 3.0 else '🔴')
        dims_str = "  ".join(f"{scores[d]:>7}" for d in DIMS)
        print(f"  {agent['label']:<22}  {star} {overall:>4.1f}  {dims_str}")

    print()
    for agent in AGENTS:
        if agent['key'] not in results:
            continue
        print(f"  {agent['label']}: {results[agent['key']]['summary']}")
    print(f"\n  Saved → {SCORES_FILE}\n")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'═'*60}")
    print(f"  🤖  AGENT BENCHMARK — LLM-as-Judge")
    print(f"  {datetime.now().strftime('%A, %B %d %Y  %H:%M')}")
    print(f"{'═'*60}\n")

    results = run_benchmark()
    if not results:
        return

    timestamp   = datetime.now().isoformat(timespec='seconds')
    all_records = load_scores()
    all_records.append({'timestamp': timestamp, 'agents': results})
    save_scores(all_records)

    print_report(results, timestamp)

if __name__ == '__main__':
    main()
