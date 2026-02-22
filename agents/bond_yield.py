"""
Agent E – 10-Year Treasury Yield Monitor
Fetches the current US 10-year yield (^TNX) via yfinance.
Shows current rate, daily change in basis points, and investor context.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import yfinance as yf
from datetime import datetime


def get_10y_yield() -> dict | None:
    """Fetch current and previous close for ^TNX. Returns dict or None."""
    try:
        hist = yf.Ticker('^TNX').history(period='5d')
        if hist.empty:
            return None
        current = round(float(hist['Close'].iloc[-1]), 3)
        prev    = round(float(hist['Close'].iloc[-2]), 3) if len(hist) >= 2 else None
        change  = round(current - prev, 3) if prev is not None else None
        bps     = round(change * 100, 1)   if change is not None else None
        return {'yield': current, 'prev': prev, 'change': change, 'bps': bps}
    except Exception:
        return None


def yield_context(y: float) -> str:
    if y < 2.5:
        return 'Very low — historically accommodative, supportive of equities'
    elif y < 3.5:
        return 'Low-moderate — broadly supportive for growth stocks'
    elif y < 4.0:
        return 'Moderate — neutral; watch for direction'
    elif y < 4.5:
        return 'Elevated — pressure on valuations, especially high-growth names'
    elif y < 5.0:
        return 'High — restrictive; watch rate-sensitive sectors (tech, real estate)'
    else:
        return 'Very high — significant headwind for growth stocks; recession risk watch'


def main():
    print(f"\n{'═'*60}")
    print(f"  📈  10-YEAR TREASURY YIELD")
    print(f"  {datetime.now().strftime('%A, %B %d %Y  %H:%M')}")
    print(f"{'═'*60}\n")

    data = get_10y_yield()
    if not data:
        print('  ✗ Could not fetch yield data.\n')
        return

    y      = data['yield']
    change = data['change']
    bps    = data['bps']

    if change is None:
        arrow, sign = '─', ''
    elif change > 0:
        arrow, sign = '▲', '+'
    else:
        arrow, sign = '▼', ''

    print(f"  Current Yield : {y:.3f}%")
    if change is not None:
        print(f"  Daily Change  : {arrow} {sign}{bps:.1f} bps  ({sign}{change:.3f}%)")
    print(f"  Context       : {yield_context(y)}")
    print()


if __name__ == '__main__':
    main()
