"""
Agent C – Price Threshold Alerts
Fetches current prices and alerts when they cross configured up/down levels.
Data source: yfinance (free, no API key)
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import yfinance as yf
import json
from datetime import datetime
import os

THRESHOLDS_FILE = os.path.expanduser('~/investment-agents/config/thresholds.json')

DEFAULT_THRESHOLDS = {
    'AAPL':  {'above': 240, 'below': 180},
    'NVDA':  {'above': 160, 'below': 100},
    'MSFT':  {'above': 460, 'below': 370},
    'GOOGL': {'above': 210, 'below': 160},
    'META':  {'above': 700, 'below': 520},
    'TSLA':  {'above': 400, 'below': 250},
}

def load_thresholds() -> dict:
    if os.path.exists(THRESHOLDS_FILE):
        with open(THRESHOLDS_FILE) as f:
            return json.load(f)
    # Write defaults on first run
    os.makedirs(os.path.dirname(THRESHOLDS_FILE), exist_ok=True)
    with open(THRESHOLDS_FILE, 'w') as f:
        json.dump(DEFAULT_THRESHOLDS, f, indent=2)
    return DEFAULT_THRESHOLDS

def get_price_and_info(ticker: str) -> tuple[float | None, str]:
    """Returns (current_price, company_name)."""
    try:
        t    = yf.Ticker(ticker)
        hist = t.history(period='1d')
        if hist.empty:
            return None, ticker
        price   = round(float(hist['Close'].iloc[-1]), 2)
        company = (t.info or {}).get('shortName', ticker)
        return price, company
    except Exception:
        return None, ticker

def pct(price: float, threshold: float) -> str:
    diff = (price - threshold) / threshold * 100
    return f"{diff:+.1f}%"

def main():
    print(f"\n{'═'*64}")
    print(f"  🚨  PRICE THRESHOLD ALERTS")
    print(f"  {datetime.now().strftime('%A, %B %d %Y  %H:%M')}")
    print(f"{'═'*64}\n")

    thresholds = load_thresholds()
    triggered  = []
    within     = []
    failed     = []

    for ticker, levels in thresholds.items():
        price, company = get_price_and_info(ticker)
        if price is None:
            failed.append(ticker)
            continue

        above = levels.get('above')
        below = levels.get('below')

        if above and price >= above:
            triggered.append({
                'ticker': ticker, 'company': company, 'price': price,
                'level': above, 'direction': 'ABOVE ↑', 'icon': '📈',
                'distance': pct(price, above),
            })
        elif below and price <= below:
            triggered.append({
                'ticker': ticker, 'company': company, 'price': price,
                'level': below, 'direction': 'BELOW ↓', 'icon': '📉',
                'distance': pct(price, below),
            })
        else:
            within.append({
                'ticker': ticker, 'company': company, 'price': price,
                'above': above, 'below': below,
            })

    # ── Triggered alerts ──────────────────────────────────────
    if triggered:
        print(f"  🚨  {len(triggered)} THRESHOLD(S) BREACHED:\n")
        for a in triggered:
            print(f"    {a['icon']}  {a['ticker']:<8}  ${a['price']:.2f}  "
                  f"{a['direction']} ${a['level']}  ({a['distance']} from threshold)")
            print(f"         {a['company']}")
        print()
    else:
        print("  ✅  No thresholds breached.\n")

    # ── Within range ──────────────────────────────────────────
    if within:
        print("  📊  Within range:\n")
        print(f"    {'Ticker':<8}  {'Price':>8}  {'Below':>8}  {'Above':>8}  {'Company'}")
        print(f"    {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*25}")
        for w in within:
            below_str = f"${w['below']}" if w['below'] else '  —'
            above_str = f"${w['above']}" if w['above'] else '  —'
            print(f"    {w['ticker']:<8}  ${w['price']:>7.2f}  {below_str:>8}  {above_str:>8}  {w['company'][:25]}")
        print()

    if failed:
        print(f"  ⚠️  Could not fetch price for: {', '.join(failed)}\n")

    print(f"  Edit thresholds: ~/investment-agents/config/thresholds.json\n")
    print(f'  Format: {{"TICKER": {{"above": 999, "below": 111}}}}\n')

if __name__ == '__main__':
    main()
