"""
Agent D – Daily News Summary (Top 3, ≤200 words)
Fetches market news via yfinance and summarizes the 3 most market-moving
items using Groq (free tier, llama-3.1-8b-instant).
Requires: GROQ_API_KEY environment variable
  Get a free key at: https://console.groq.com
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import yfinance as yf
import requests
import os
import json
from pathlib import Path
from datetime import datetime

def _load_groq_key() -> str:
    try:
        cfg = json.loads((Path.home() / 'investment-agents/config/email_config.json').read_text())
        return cfg.get('groq_api_key', '')
    except Exception:
        return ''

GROQ_KEY = _load_groq_key() or os.environ.get('GROQ_API_KEY', '')

# Tickers to pull news from — broad market coverage
NEWS_TICKERS = ['SPY', 'QQQ', 'DIA', 'AAPL', 'MSFT', 'NVDA', 'META', 'TSLA', 'AMZN', 'GOOGL']

def fetch_market_news(max_items: int = 20) -> list[dict]:
    """Collect recent headlines from major market tickers, deduplicated.
    Handles both the legacy flat structure and the newer nested 'content' structure."""
    articles   = []
    seen_titles: set[str] = set()

    for ticker in NEWS_TICKERS:
        try:
            news = yf.Ticker(ticker).news or []
            for item in news:
                # New nested structure: item['content']['title']
                content = item.get('content', item)  # fall back to item itself for legacy
                title   = content.get('title', '').strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                # Publisher may be nested under content.provider
                provider  = content.get('provider', {})
                publisher = provider.get('displayName', '') if isinstance(provider, dict) else ''
                publisher = publisher or item.get('publisher', '')

                summary = content.get('summary', '') or content.get('description', '')

                articles.append({
                    'title':     title,
                    'publisher': publisher,
                    'summary':   summary[:300],
                })
                if len(articles) >= max_items:
                    return articles
        except Exception:
            continue

    return articles

def summarize_with_groq(articles: list[dict]) -> str:
    """Use Groq (free) to pick and summarize the 3 most market-moving items."""
    api_key = GROQ_KEY

    headlines = '\n'.join(
        f"- {a['title']} [{a['publisher']}]"
        + (f"\n  {a['summary']}" if a['summary'] else '')
        for a in articles
    )

    response = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': 'llama-3.1-8b-instant',
            'max_tokens': 350,
            'temperature': 0.3,
            'messages': [{
                'role': 'user',
                'content': (
                    "You are a concise financial news editor. "
                    "From the headlines below, select the 3 items most likely to move markets today. "
                    "Write a numbered summary in 200 words or less total. "
                    "Each item: bold the company/topic, then 1-2 sentences on why it matters for investors. "
                    "No fluff, no intro sentence, go straight to item 1.\n\n"
                    f"{headlines}"
                ),
            }],
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content'].strip()

def market_mood(summary: str) -> str:
    """Simple keyword-based mood indicator."""
    s = summary.lower()
    bullish  = sum(s.count(w) for w in ['surge', 'rally', 'beat', 'record', 'gain', 'rise', 'strong', 'growth'])
    bearish  = sum(s.count(w) for w in ['fall', 'drop', 'miss', 'concern', 'fear', 'risk', 'weak', 'decline'])
    if bullish > bearish + 1:
        return '🟢 Bullish'
    elif bearish > bullish + 1:
        return '🔴 Bearish / Risk-off'
    return '🟡 Mixed / Neutral'

def main():
    print(f"\n{'═'*60}")
    print(f"  📰  DAILY MARKET NEWS — Top 3")
    print(f"  {datetime.now().strftime('%A, %B %d %Y  %H:%M')}")
    print(f"{'═'*60}\n")

    if not GROQ_KEY:
        print("  ✗ Groq API key not found.")
        print("  Set groq_api_key in ~/investment-agents/config/email_config.json\n")
        return

    articles = fetch_market_news()
    if not articles:
        print("  ✗ Could not fetch any news articles.\n")
        return

    print(f"  Analysing {len(articles)} headlines...\n")

    summary = summarize_with_groq(articles)
    print(summary)
    print(f"\n  ─────────────────────────────")
    print(f"  Market Mood: {market_mood(summary)}")
    print()

if __name__ == '__main__':
    main()
