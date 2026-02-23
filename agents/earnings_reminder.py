"""
Agent B – Earnings 7-Day Reminder
Alerts when a watchlist stock has earnings in the next 7 days.
Data source: yfinance (free, no API key)
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import yfinance as yf
import json
from datetime import datetime, timedelta
import os

WATCHLIST_FILE = os.path.expanduser('~/investment-agents/config/watchlist.json')

DEFAULT_WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']

def load_watchlist() -> list:
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE) as f:
            return json.load(f)
    return DEFAULT_WATCHLIST

def get_earnings_info(ticker: str) -> dict | None:
    """Returns next earnings date info or None."""
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar
        info = t.info or {}
        company = info.get('shortName', ticker)

        if cal is None:
            return None

        dates = cal.get('Earnings Date', [])
        if hasattr(dates, 'tolist'):
            dates = dates.tolist()
        if not dates:
            return None

        next_date = dates[0]
        if hasattr(next_date, 'date'):
            next_date = next_date.date()
        else:
            next_date = datetime.strptime(str(next_date)[:10], '%Y-%m-%d').date()

        days_away = (next_date - datetime.now().date()).days
        return {'ticker': ticker, 'company': company, 'date': next_date, 'days': days_away}

    except Exception:
        return None

def main():
    today      = datetime.now().date()
    window_date = today + timedelta(days=7)

    print(f"\n{'═'*60}")
    print(f"  🔔  EARNINGS 7-DAY REMINDER")
    print(f"  {datetime.now().strftime('%A, %B %d %Y  %H:%M')}")
    print(f"  Checking for earnings on or before: {window_date}")
    print(f"{'═'*60}\n")

    watchlist = load_watchlist()
    print(f"  Watchlist ({len(watchlist)}): {', '.join(watchlist)}\n")

    alerts   = []   # earnings in 0–2 days
    upcoming = []   # earnings 3–30 days away
    errors   = []

    for ticker in watchlist:
        info = get_earnings_info(ticker)
        if info is None:
            errors.append(ticker)
            continue
        days = info['days']
        if 0 <= days <= 7:
            alerts.append(info)
        elif 8 <= days <= 30:
            upcoming.append(info)

    # ── Alerts ────────────────────────────────────────────────
    if alerts:
        print(f"  🚨  {len(alerts)} ALERT(S) — Earnings within 7 days:\n")
        for a in sorted(alerts, key=lambda x: x['days']):
            if a['days'] == 0:
                label = '🔴 TODAY'
            elif a['days'] == 1:
                label = '⚡ TOMORROW'
            else:
                label = f"📅 in {a['days']} days ({a['date']})"
            print(f"    {a['ticker']:<8}  {a['company'][:35]:<35}  {label}")
        print()
    else:
        print("  ✅  No earnings in the next 7 days for your watchlist.\n")

    # ── Upcoming (3–30 days) ───────────────────────────────────
    if upcoming:
        print("  📆  Upcoming earnings (8–30 days):\n")
        for a in sorted(upcoming, key=lambda x: x['days']):
            print(f"    {a['ticker']:<8}  {a['company'][:35]:<35}  {a['date']}  (in {a['days']} days)")
        print()

    if errors:
        print(f"  ⚠️  Could not fetch earnings for: {', '.join(errors)}\n")

    print(f"  Edit watchlist: ~/investment-agents/config/watchlist.json\n")

if __name__ == '__main__':
    main()
