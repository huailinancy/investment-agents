"""
Agent A – IPO Scout (Tech)
Fetches upcoming IPOs, filters for tech sector, flags new ones since last run.
Data source: stockanalysis.com (free, no API key)
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
import sys

STATE_FILE  = os.path.expanduser('~/investment-agents/state/ipo_seen.json')
CONFIG_FILE = os.path.expanduser('~/investment-agents/config/ipo_config.json')

DEFAULT_TECH_KEYWORDS = [
    'tech', 'software', 'ai', 'artificial intelligence', 'data', 'cloud',
    'cyber', 'saas', 'semiconductor', 'fintech', 'digital', 'platform',
    'internet', 'computing', 'analytics', 'robotics', 'biotech', 'medtech',
    'automation', 'electric', 'ev', 'satellite', 'drone', 'quantum',
]

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {'tech_keywords': DEFAULT_TECH_KEYWORDS}

def load_seen() -> set:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen: set):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(sorted(seen), f, indent=2)

def is_tech(name: str, keywords: list) -> bool:
    name_lower = name.lower()
    return any(kw in name_lower for kw in keywords)

def fetch_upcoming_ipos() -> list:
    year = datetime.now().year
    url  = f'https://stockanalysis.com/ipos/{year}/'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f'  ✗ Could not fetch IPO data: {e}')
        return []

    soup = BeautifulSoup(res.text, 'html.parser')
    tables = soup.find_all('table')
    ipos   = []

    # The year page has 2 tables: [0] recent IPOs, [1] upcoming IPOs
    # Fall back to any table if layout changes
    upcoming_table = tables[1] if len(tables) >= 2 else (tables[0] if tables else None)
    if not upcoming_table:
        return ipos

    # Detect column order from header row
    header_row = upcoming_table.find('tr')
    headers_text = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])] if header_row else []

    def col(cols, *keys):
        for k in keys:
            for i, h in enumerate(headers_text):
                if k in h and i < len(cols):
                    return cols[i].get_text(strip=True)
        return '—'

    rows = upcoming_table.find_all('tr')[1:]
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 2:
            continue
        # Flexible extraction: works regardless of column order
        date   = col(cols, 'date')
        symbol = col(cols, 'symbol', 'ticker')
        name   = col(cols, 'name', 'company')
        price  = col(cols, 'price', 'range')
        # Fallback positional if no headers matched
        if date == '—' and name == '—':
            date   = cols[0].get_text(strip=True) if len(cols) > 0 else '—'
            symbol = cols[1].get_text(strip=True) if len(cols) > 1 else '—'
            name   = cols[2].get_text(strip=True) if len(cols) > 2 else '—'
            price  = cols[3].get_text(strip=True) if len(cols) > 3 else '—'
        if name and name != '—':
            ipos.append({'name': name, 'symbol': symbol, 'date': date, 'price_range': price})

    return ipos

def main():
    sector_filter = ' '.join(sys.argv[1:]).strip() if len(sys.argv) > 1 else ''
    config   = load_config()
    keywords = config['tech_keywords']
    if sector_filter:
        keywords = [sector_filter.lower()] + keywords

    seen = load_seen()
    ipos = fetch_upcoming_ipos()

    print(f"\n{'═'*62}")
    print(f"  🔍  IPO SCOUT — Upcoming Tech IPOs")
    print(f"  {datetime.now().strftime('%A, %B %d %Y  %H:%M')}")
    print(f"{'═'*62}\n")

    tech_ipos = [ipo for ipo in ipos if is_tech(ipo['name'], keywords)]

    if not tech_ipos:
        print('  No upcoming tech IPOs found at this time.\n')
        return

    new_count = 0
    new_seen  = set(seen)

    print(f"  {'':4}  {'Symbol':<8}  {'Company':<32}  {'Date':<14}  {'Price Range'}")
    print(f"  {'─'*4}  {'─'*8}  {'─'*32}  {'─'*14}  {'─'*14}")

    for ipo in tech_ipos:
        is_new = ipo['symbol'] not in seen and ipo['symbol'] != '—'
        if is_new:
            new_count += 1
            new_seen.add(ipo['symbol'])
            tag = '⭐'
        else:
            tag = '  '

        name_trunc = ipo['name'][:32]
        print(f"  {tag:4}  {ipo['symbol']:<8}  {name_trunc:<32}  {ipo['date']:<14}  {ipo['price_range']}")

    print(f"\n  {len(tech_ipos)} tech IPO(s) upcoming.  ⭐ {new_count} new since last run.\n")

    save_seen(new_seen | {ipo['symbol'] for ipo in tech_ipos if ipo['symbol'] != '—'})

if __name__ == '__main__':
    main()
