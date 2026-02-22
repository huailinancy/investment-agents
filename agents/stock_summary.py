"""
Stock News Summary — ALAB (Astera Labs) & IT (Gartner)
Fetches public news for these two tickers and uses Groq to summarize
into up to 3 bullets about price movement reasons.
- No duplicate topics
- 📈/📉 sign at start of each bullet
- Clickable source link per bullet
- Skips entirely if Groq judges there is nothing impactful.

Requires: groq_api_key in ~/investment-agents/config/email_config.json
          (or GROQ_API_KEY environment variable)
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import os, json, re, requests
from pathlib import Path
from datetime import datetime

import yfinance as yf

# ── Config ────────────────────────────────────────────────────────────────────
BASE      = Path.home() / 'investment-agents'
EMAIL_CFG = BASE / 'config' / 'email_config.json'

def _load_groq_key() -> str:
    try:
        cfg = json.loads(EMAIL_CFG.read_text())
        return cfg.get('groq_api_key', '')
    except Exception:
        return ''

GROQ_KEY      = _load_groq_key() or os.environ.get('GROQ_API_KEY', '')
STOCK_TICKERS = {'ALAB': 'Astera Labs', 'IT': 'Gartner'}

# ── News Fetching ─────────────────────────────────────────────────────────────
def fetch_stock_news(max_per_ticker: int = 10) -> list:
    """
    Returns a flat, deduplicated list of article dicts across ALAB and IT.
    Each dict: {idx, ticker, company, title, summary, url}
    """
    articles, seen = [], set()
    for ticker, company in STOCK_TICKERS.items():
        try:
            for item in (yf.Ticker(ticker).news or []):
                content = item.get('content', item)
                title   = content.get('title', '').strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                summary = content.get('summary', '') or content.get('description', '')
                url = (
                    (content.get('canonicalUrl') or {}).get('url')
                    or (content.get('clickThroughUrl') or {}).get('url')
                    or content.get('link', '')
                    or item.get('link', '')
                    or ''
                )
                articles.append({
                    'idx':     len(articles) + 1,
                    'ticker':  ticker,
                    'company': company,
                    'title':   title,
                    'summary': summary[:300],
                    'url':     url,
                })
                if sum(1 for a in articles if a['ticker'] == ticker) >= max_per_ticker:
                    break
        except Exception:
            pass
    return articles

# ── Groq Summarization ────────────────────────────────────────────────────────
def summarize_with_groq(articles: list) -> str | None:
    """
    Returns bullet lines or None if nothing impactful.
    Bullets include [UP]/[DOWN] direction and [ref:N] source reference.
    """
    if not GROQ_KEY or not articles:
        return None

    alab_lines = [a for a in articles if a['ticker'] == 'ALAB'][:5]
    it_lines   = [a for a in articles if a['ticker'] == 'IT'][:5]

    def fmt(a):
        snippet = f' — {a["summary"][:150]}' if a['summary'] else ''
        return f'[{a["idx"]}] {a["title"]}{snippet}'

    prompt = (
        "You are a stock analyst. Write bullet-point summaries for ALAB and IT.\n\n"
        "FORMAT — each bullet must look exactly like these examples:\n"
        "- UP ALAB **Price Target Raised** — BofA raised target to $200, boosting sentiment [ref:2]\n"
        "- DOWN IT **Earnings Miss** — Weak Q4 EPS may pressure stock lower [ref:11]\n\n"
        "RULES:\n"
        "- UP = price likely rises, DOWN = price likely falls\n"
        "- Bold only the short topic using **double asterisks**\n"
        "- End each bullet with [ref:N] — the headline number\n"
        "- Max 3 bullets for ALAB, max 3 for IT — no duplicates\n"
        "- Skip a ticker entirely if its headlines are not impactful\n"
        "- If NEITHER ticker has impactful news, output only: NO_IMPACT\n"
        "- No numbered lists, no section headers, no extra text\n\n"
        "=== ALAB (Astera Labs) headlines ===\n"
        + '\n'.join(fmt(a) for a in alab_lines)
        + "\n\n=== IT (Gartner) headlines ===\n"
        + '\n'.join(fmt(a) for a in it_lines)
    )

    try:
        res = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_KEY}', 'Content-Type': 'application/json'},
            json={
                'model':       'llama-3.1-8b-instant',
                'max_tokens':  600,
                'temperature': 0.3,
                'messages':    [{'role': 'user', 'content': prompt}],
            },
            timeout=30,
        )
        res.raise_for_status()
        text = res.json()['choices'][0]['message']['content'].strip()
    except Exception:
        return None

    return None if text.upper().startswith('NO_IMPACT') else text

# ── Standalone Main ───────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  STOCK NEWS SUMMARY — ALAB & IT (Gartner)")
    print(f"  {datetime.now().strftime('%A, %B %d %Y  %H:%M')}")
    print(f"{'='*60}\n")

    if not GROQ_KEY:
        print("  [!] Groq API key not found.")
        print("      Set groq_api_key in ~/investment-agents/config/email_config.json\n")
        return

    print("  Fetching news for ALAB and IT...")
    articles = fetch_stock_news()

    if not articles:
        print("  No news articles found for either ticker.\n")
        return

    print(f"  Found {len(articles)} unique article(s). Asking Groq to assess impact...\n")
    summary = summarize_with_groq(articles)

    if summary is None:
        print("  Nothing impactful found — section skipped in daily report.\n")
        return

    from collections import defaultdict
    url_map      = {a['idx']: a['url'] for a in articles}
    bullets_raw  = [l.strip() for l in summary.splitlines()
                    if l.strip().startswith('-') and 'NO_IMPACT' not in l.upper()]

    # Deduplicate by bold topic, group max 3 per ticker
    ticker_lower = {t.lower() for t in STOCK_TICKERS}
    seen_topics  = set()
    by_ticker    = defaultdict(list)
    for b in bullets_raw:
        topics = [m.lower().strip() for m in re.findall(r'\*\*(.+?)\*\*', b)
                  if m.lower().strip() not in ticker_lower]
        if any(t in seen_topics for t in topics):
            continue
        seen_topics.update(topics)
        for t in STOCK_TICKERS:
            if re.search(r'\b' + t + r'\b', b):
                by_ticker[t].append(b)
                break

    final_bullets = []
    for t in STOCK_TICKERS:
        final_bullets.extend(by_ticker[t][:3])

    for b in final_bullets:
        content_str = b[1:].strip()

        dir_match  = re.match(r'\[?(UP|DOWN)\]?\s*', content_str, re.IGNORECASE)
        direction  = dir_match.group(1).upper() if dir_match else None
        if dir_match:
            content_str = content_str[dir_match.end():]

        ref_match   = re.search(r'\[ref:(\d+)\]\s*$', content_str, re.IGNORECASE)
        article_url = url_map.get(int(ref_match.group(1)), '') if ref_match else ''
        if ref_match:
            content_str = content_str[:ref_match.start()].strip()

        plain_text = re.sub(r'\*\*(.+?)\*\*', r'\1', content_str)
        icon       = '📈' if direction == 'UP' else ('📉' if direction == 'DOWN' else '•')
        url_str    = f'\n     {article_url}' if article_url else ''
        print(f"  {icon} {plain_text}{url_str}\n")

if __name__ == '__main__':
    main()
