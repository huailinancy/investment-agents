"""
Daily Investment Report — runs all 4 agents and sends one email.

Sections (only included when relevant):
  1. 📰 Market News          — top 3 stories via Groq
  2. 📈 10-Year Treasury     — current yield, daily change in bps, investor context
  3. 📅 Upcoming Earnings    — next 7 days from watchlist
  4. 🚨 Price Alerts         — ALAB & Gartner (IT) only, skipped if neither is above threshold
  5. 📰 Stock News Summary   — ALAB & IT bullets via Groq, skipped if nothing impactful
  6. 🔍 Upcoming Tech IPOs   — skipped if none found
  7. 🤖 Agent Benchmark      — last saved scores from benchmark.py, skipped if no results yet

Schedule: Windows Task Scheduler at 08:00 daily.
Config:   ~/investment-agents/config/email_config.json
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import os, json, smtplib, requests
from datetime import datetime, timedelta, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import yfinance as yf
from bs4 import BeautifulSoup

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE        = Path.home() / 'investment-agents'
CONFIG_DIR  = BASE / 'config'
STATE_DIR   = BASE / 'state'
EMAIL_CFG   = CONFIG_DIR / 'email_config.json'
WATCHLIST_F = CONFIG_DIR / 'watchlist.json'
IPO_CFG_F   = CONFIG_DIR / 'ipo_config.json'
IPO_STATE_F = STATE_DIR  / 'ipo_seen.json'

# ── Load config ───────────────────────────────────────────────────────────────
def load_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default

cfg       = load_json(EMAIL_CFG, {})
GROQ_KEY  = cfg.get('groq_api_key', os.environ.get('GROQ_API_KEY', ''))
WATCHLIST = load_json(WATCHLIST_F, ['AMZN','MSFT','NVDA','HOOD','TSM','RIVN','IT','TSLA','SMCI','AMD','ALAB','VRTX','CRM'])
IPO_KW    = load_json(IPO_CFG_F, {}).get('tech_keywords', ['tech','software','ai','data','cloud','cyber','saas','semiconductor','fintech','digital','platform','internet','analytics','automation','ev','drone','quantum'])

# Stocks watched for price alerts (only these two go into the email)
ALERT_TICKERS = {
    'ALAB': {'above': 180, 'below': None},
    'IT':   {'above': 200, 'below': None},
}

# ── Helper ────────────────────────────────────────────────────────────────────
def get_price(ticker: str):
    try:
        hist = yf.Ticker(ticker).history(period='1d')
        return round(float(hist['Close'].iloc[-1]), 2) if not hist.empty else None
    except Exception:
        return None

def ticker_name(ticker: str) -> str:
    try:
        return yf.Ticker(ticker).info.get('shortName', ticker)
    except Exception:
        return ticker

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — Market News (Agent D logic)
# ─────────────────────────────────────────────────────────────────────────────
NEWS_TICKERS = ['SPY','QQQ','DIA','AAPL','MSFT','NVDA','META','TSLA','AMZN','GOOGL']

def fetch_market_news(max_items=20):
    articles, seen = [], set()
    for t in NEWS_TICKERS:
        try:
            for item in (yf.Ticker(t).news or []):
                content   = item.get('content', item)
                title     = content.get('title', '').strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                provider  = content.get('provider', {})
                publisher = (provider.get('displayName', '') if isinstance(provider, dict) else '') or item.get('publisher', '')
                summary   = content.get('summary', '') or content.get('description', '')
                articles.append({'title': title, 'publisher': publisher, 'summary': summary[:300]})
                if len(articles) >= max_items:
                    return articles
        except Exception:
            continue
    return articles

def build_news_section() -> tuple[str, str]:
    """Returns (html_block, plain_block). Empty strings if API key missing."""
    if not GROQ_KEY:
        return '', '  [Groq API key not configured — skipping market news]\n'

    articles = fetch_market_news()
    if not articles:
        return '', '  Could not fetch news.\n'

    headlines = '\n'.join(
        f"- {a['title']} [{a['publisher']}]" + (f"\n  {a['summary']}" if a['summary'] else '')
        for a in articles
    )
    try:
        res = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': 'llama-3.1-8b-instant',
                'max_tokens': 350,
                'temperature': 0.3,
                'messages': [{'role': 'user', 'content': (
                    "You are a concise financial news editor. "
                    "From the headlines below, pick the 3 most market-moving items. "
                    "Write a numbered summary in 200 words or less. "
                    "Each item: bold the company/topic (use **bold**), then 1-2 sentences on why it matters. "
                    "No intro sentence — start directly with '1.'.\n\n" + headlines
                )}],
            },
            timeout=30,
        )
        res.raise_for_status()
        text = res.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return '', f'  News summary failed: {e}\n'

    # Detect market mood
    s = text.lower()
    bull = sum(s.count(w) for w in ['surge','rally','beat','record','gain','rise','strong','growth'])
    bear = sum(s.count(w) for w in ['fall','drop','miss','concern','fear','risk','weak','decline'])
    if bull > bear + 1:
        mood, mood_color = '🟢 Bullish', '#22c55e'
    elif bear > bull + 1:
        mood, mood_color = '🔴 Bearish / Risk-off', '#ef4444'
    else:
        mood, mood_color = '🟡 Mixed / Neutral', '#eab308'

    # Convert **bold** to <strong> for HTML
    import re
    html_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    html_text = html_text.replace('\n', '<br>')

    html = (
        f'<p style="white-space:pre-line">{html_text}</p>'
        f'<p style="margin-top:8px"><strong>Market Mood:</strong> '
        f'<span style="color:{mood_color}">{mood}</span></p>'
    )
    plain = text + f'\n\nMarket Mood: {mood}\n'
    return html, plain

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — 10-Year Treasury Yield
# ─────────────────────────────────────────────────────────────────────────────
def get_10y_yield() -> dict | None:
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
    if y < 2.5:   return 'Very low — historically accommodative, supportive of equities'
    elif y < 3.5: return 'Low-moderate — broadly supportive for growth stocks'
    elif y < 4.0: return 'Moderate — neutral; watch for direction'
    elif y < 4.5: return 'Elevated — pressure on valuations, especially high-growth names'
    elif y < 5.0: return 'High — restrictive; watch rate-sensitive sectors (tech, real estate)'
    else:          return 'Very high — significant headwind for growth stocks'

def build_bond_section() -> tuple[str, str]:
    data = get_10y_yield()
    if not data:
        return ('<p style="color:#6b7280">Could not fetch yield data.</p>',
                '  Could not fetch yield data.\n')

    y      = data['yield']
    change = data['change']
    bps    = data['bps']

    if change is None:
        arrow, sign, color = '─', '', '#6b7280'
    elif change > 0:
        arrow, sign, color = '▲', '+', '#ef4444'   # rising yield = red (pressure on stocks)
    else:
        arrow, sign, color = '▼', '', '#22c55e'    # falling yield = green (relief for stocks)

    change_str = f'{arrow} {sign}{bps:.1f} bps ({sign}{change:.3f}%)' if change is not None else '─'
    context    = yield_context(y)

    html = (
        f'<table style="border-collapse:collapse">'
        f'<tr><td style="padding:6px 16px 6px 0;color:#6b7280">Current Yield</td>'
        f'<td style="padding:6px 0;font-size:22px;font-weight:700">{y:.3f}%</td></tr>'
        f'<tr><td style="padding:6px 16px 6px 0;color:#6b7280">Daily Change</td>'
        f'<td style="padding:6px 0;font-weight:600;color:{color}">{change_str}</td></tr>'
        f'<tr><td style="padding:6px 16px 6px 0;color:#6b7280;vertical-align:top">Context</td>'
        f'<td style="padding:6px 0">{context}</td></tr>'
        f'</table>'
    )
    plain = (
        f'  Current Yield : {y:.3f}%\n'
        f'  Daily Change  : {change_str}\n'
        f'  Context       : {context}\n'
    )
    return html, plain

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — Upcoming Earnings (next 7 days)
# ─────────────────────────────────────────────────────────────────────────────
def get_earnings_date(ticker: str):
    try:
        cal   = yf.Ticker(ticker).calendar
        if cal is None:
            return None
        dates = cal.get('Earnings Date', [])
        if hasattr(dates, 'tolist'):
            dates = dates.tolist()
        if not dates:
            return None
        d = dates[0]
        return d.date() if hasattr(d, 'date') else datetime.strptime(str(d)[:10], '%Y-%m-%d').date()
    except Exception:
        return None

def build_earnings_section() -> tuple[str, str]:
    today    = date.today()
    cutoff   = today + timedelta(days=7)
    upcoming = []

    for ticker in WATCHLIST:
        d = get_earnings_date(ticker)
        if d and today <= d <= cutoff:
            days_away = (d - today).days
            name = ticker_name(ticker)
            upcoming.append((days_away, ticker, name, d))

    if not upcoming:
        html  = '<p style="color:#6b7280">No earnings from your watchlist in the next 7 days.</p>'
        plain = '  No earnings from your watchlist in the next 7 days.\n'
        return html, plain

    upcoming.sort()
    rows_html  = ''
    rows_plain = ''
    for days, ticker, name, d in upcoming:
        if days == 0:
            label, badge = 'TODAY 🔴', '#ef4444'
        elif days == 1:
            label, badge = 'TOMORROW ⚡', '#f97316'
        else:
            label, badge = f'in {days} days', '#6b7280'
        rows_html  += (
            f'<tr><td style="padding:6px 12px;font-weight:600">{ticker}</td>'
            f'<td style="padding:6px 12px">{name}</td>'
            f'<td style="padding:6px 12px">{d}</td>'
            f'<td style="padding:6px 12px;color:{badge};font-weight:600">{label}</td></tr>'
        )
        rows_plain += f'  {ticker:<8} {name[:35]:<35} {str(d):<12} {label}\n'

    html = (
        '<table style="border-collapse:collapse;width:100%">'
        '<tr style="background:#f3f4f6"><th style="padding:6px 12px;text-align:left">Ticker</th>'
        '<th style="padding:6px 12px;text-align:left">Company</th>'
        '<th style="padding:6px 12px;text-align:left">Date</th>'
        '<th style="padding:6px 12px;text-align:left">When</th></tr>'
        + rows_html + '</table>'
    )
    return html, rows_plain

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — Price Alerts (ALAB & IT only, skip if none triggered)
# ─────────────────────────────────────────────────────────────────────────────
def build_price_section() -> tuple[str, str]:
    triggered = []
    for ticker, levels in ALERT_TICKERS.items():
        price = get_price(ticker)
        if price is None:
            continue
        above = levels.get('above')
        below = levels.get('below')
        name  = ticker_name(ticker)
        if above and price >= above:
            pct = (price - above) / above * 100
            triggered.append((ticker, name, price, f'ABOVE ${above}', f'+{pct:.1f}%', '#22c55e', '📈'))
        elif below and price <= below:
            pct = (price - below) / below * 100
            triggered.append((ticker, name, price, f'BELOW ${below}', f'{pct:.1f}%', '#ef4444', '📉'))

    if not triggered:
        return '', ''   # skip section entirely

    rows_html  = ''
    rows_plain = ''
    for ticker, name, price, direction, pct, color, icon in triggered:
        rows_html  += (
            f'<tr><td style="padding:6px 12px">{icon} <strong>{ticker}</strong></td>'
            f'<td style="padding:6px 12px">{name}</td>'
            f'<td style="padding:6px 12px;font-weight:600">${price:.2f}</td>'
            f'<td style="padding:6px 12px;color:{color};font-weight:600">{direction} ({pct})</td></tr>'
        )
        rows_plain += f'  {icon} {ticker:<8} ${price:.2f}  {direction} ({pct})\n'

    html = (
        '<table style="border-collapse:collapse;width:100%">'
        '<tr style="background:#fef2f2"><th style="padding:6px 12px;text-align:left">Ticker</th>'
        '<th style="padding:6px 12px;text-align:left">Company</th>'
        '<th style="padding:6px 12px;text-align:left">Price</th>'
        '<th style="padding:6px 12px;text-align:left">Alert</th></tr>'
        + rows_html + '</table>'
    )
    return html, rows_plain

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — Stock News Summary (ALAB & IT, skip if nothing impactful)
# ─────────────────────────────────────────────────────────────────────────────
STOCK_SUMMARY_TICKERS = {'ALAB': 'Astera Labs', 'IT': 'Gartner'}

def fetch_stock_summary_news(max_per_ticker: int = 10) -> list:
    """
    Returns a flat, deduplicated list of article dicts across ALAB and IT.
    Each dict: {idx, ticker, company, title, summary, url}
    """
    articles, seen = [], set()
    for ticker, company in STOCK_SUMMARY_TICKERS.items():
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

def build_stock_summary_section() -> tuple[str, str]:
    """Returns (html_block, plain_block). Returns ('', '') if nothing impactful."""
    import re as _re
    from collections import defaultdict
    if not GROQ_KEY:
        return '', ''

    articles = fetch_stock_summary_news()
    if not articles:
        return '', ''

    # Split headlines by ticker (max 5 each) for a structured prompt
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
        return '', ''

    if text.upper().startswith('NO_IMPACT'):
        return '', ''

    # Parse all bullet lines — skip any NO_IMPACT filler lines
    bullets_raw = [l.strip() for l in text.splitlines()
                   if l.strip().startswith('-') and 'NO_IMPACT' not in l.upper()]
    if not bullets_raw:
        return '', ''

    url_map = {a['idx']: a['url'] for a in articles}

    # Deduplicate by bold topic, then group max 3 per ticker
    ticker_lower = {t.lower() for t in STOCK_SUMMARY_TICKERS}
    seen_topics  = set()
    by_ticker    = defaultdict(list)
    for b in bullets_raw:
        # Collect bold phrases, excluding ticker names (they're not topics)
        topics = [m.lower().strip() for m in _re.findall(r'\*\*(.+?)\*\*', b)
                  if m.lower().strip() not in ticker_lower]
        if any(t in seen_topics for t in topics):
            continue
        seen_topics.update(topics)
        # Match ticker using word boundary to avoid 'IT' matching 'INVESTMENT' etc.
        for t in STOCK_SUMMARY_TICKERS:
            if _re.search(r'\b' + t + r'\b', b):
                by_ticker[t].append(b)
                break

    final_bullets = []
    for t in STOCK_SUMMARY_TICKERS:
        final_bullets.extend(by_ticker[t][:3])

    if not final_bullets:
        return '', ''

    html_items  = []
    plain_items = []
    for b in final_bullets:
        content_str = b[1:].strip()   # strip leading dash

        # Match UP or DOWN with or without brackets: [UP], UP, [DOWN], DOWN
        dir_match = _re.match(r'\[?(UP|DOWN)\]?\s*', content_str, _re.IGNORECASE)
        if dir_match:
            direction   = dir_match.group(1).upper()
            content_str = content_str[dir_match.end():]
        else:
            direction = None

        # Extract [ref:N] at end
        ref_match = _re.search(r'\[ref:(\d+)\]\s*$', content_str, _re.IGNORECASE)
        if ref_match:
            article_url = url_map.get(int(ref_match.group(1)), '')
            content_str = content_str[:ref_match.start()].strip()
        else:
            article_url = ''

        if direction == 'UP':
            icon, color = '📈', '#22c55e'
        elif direction == 'DOWN':
            icon, color = '📉', '#ef4444'
        else:
            icon, color = '•', '#6b7280'

        html_text  = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content_str)
        plain_text = _re.sub(r'\*\*(.+?)\*\*', r'\1', content_str)

        link_html = (
            f' <a href="{article_url}" target="_blank" '
            f'style="color:#3b82f6;font-size:12px;text-decoration:underline">↗ source</a>'
            if article_url else ''
        )

        html_items.append(
            f'<li style="margin:8px 0">'
            f'<span style="color:{color};font-weight:700">{icon}</span> '
            f'{html_text}{link_html}</li>'
        )
        plain_items.append(f'  {icon} {plain_text}\n')

    html  = f'<ul style="margin:8px 0;padding-left:20px;list-style:none">{"".join(html_items)}</ul>'
    plain = ''.join(plain_items)
    return html, plain

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — Upcoming Tech IPOs (skip if none)
# ─────────────────────────────────────────────────────────────────────────────
def is_tech(name: str) -> bool:
    return any(kw in name.lower() for kw in IPO_KW)

def load_ipo_seen() -> set:
    return set(json.loads(IPO_STATE_F.read_text())) if IPO_STATE_F.exists() else set()

def save_ipo_seen(seen: set):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    IPO_STATE_F.write_text(json.dumps(sorted(seen), indent=2))

def fetch_upcoming_ipos() -> list:
    year = datetime.now().year
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        res = requests.get(f'https://stockanalysis.com/ipos/{year}/', headers=headers, timeout=15)
        res.raise_for_status()
    except Exception:
        return []
    soup   = BeautifulSoup(res.text, 'html.parser')
    tables = soup.find_all('table')
    table  = tables[1] if len(tables) >= 2 else (tables[0] if tables else None)
    if not table:
        return []
    ipos, header_row = [], table.find('tr')
    hdr = [th.get_text(strip=True).lower() for th in header_row.find_all(['th','td'])] if header_row else []
    def col(cols, *keys):
        for k in keys:
            for i, h in enumerate(hdr):
                if k in h and i < len(cols):
                    return cols[i].get_text(strip=True)
        return '—'
    for row in table.find_all('tr')[1:]:
        cols = row.find_all('td')
        if len(cols) < 2:
            continue
        date   = col(cols, 'date') or (cols[0].get_text(strip=True) if cols else '—')
        symbol = col(cols, 'symbol', 'ticker') or (cols[1].get_text(strip=True) if len(cols)>1 else '—')
        name   = col(cols, 'name', 'company') or (cols[2].get_text(strip=True) if len(cols)>2 else '—')
        if name and name != '—':
            ipos.append({'name': name, 'symbol': symbol, 'date': date})
    return ipos

def build_ipo_section() -> tuple[str, str]:
    seen  = load_ipo_seen()
    ipos  = fetch_upcoming_ipos()
    tech  = [i for i in ipos if is_tech(i['name'])]
    if not tech:
        return '', ''   # skip section

    rows_html  = ''
    rows_plain = ''
    new_syms   = set()
    for ipo in tech:
        is_new = ipo['symbol'] not in seen and ipo['symbol'] != '—'
        if is_new:
            new_syms.add(ipo['symbol'])
        badge = ' <span style="background:#fef08a;padding:1px 6px;border-radius:4px;font-size:11px">NEW ⭐</span>' if is_new else ''
        rows_html  += (
            f'<tr><td style="padding:6px 12px;font-weight:600">{ipo["symbol"]}{badge}</td>'
            f'<td style="padding:6px 12px">{ipo["name"]}</td>'
            f'<td style="padding:6px 12px">{ipo["date"]}</td></tr>'
        )
        tag = '⭐ NEW' if is_new else '      '
        rows_plain += f'  {tag}  {ipo["symbol"]:<8} {ipo["name"][:35]:<35} {ipo["date"]}\n'

    html = (
        '<table style="border-collapse:collapse;width:100%">'
        '<tr style="background:#f0fdf4"><th style="padding:6px 12px;text-align:left">Symbol</th>'
        '<th style="padding:6px 12px;text-align:left">Company</th>'
        '<th style="padding:6px 12px;text-align:left">Expected Date</th></tr>'
        + rows_html + '</table>'
        + f'<p style="color:#6b7280;font-size:12px">{len(tech)} upcoming tech IPO(s) — {len(new_syms)} new since last report.</p>'
    )
    plain = rows_plain + f'\n  {len(tech)} upcoming tech IPO(s) — {len(new_syms)} new since last report.\n'

    # Save seen state
    save_ipo_seen(seen | {i['symbol'] for i in tech if i['symbol'] != '—'})
    return html, plain

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7 — Agent Benchmark Scorecard (reads last saved results)
# ─────────────────────────────────────────────────────────────────────────────
_BENCHMARK_DIMS = ['completeness', 'data_quality', 'relevance', 'clarity', 'error_free']
_BENCHMARK_LABELS = ['Compl.', 'Quality', 'Relev.', 'Clarity', 'No-Err']
_BENCHMARK_AGENTS = [
    ('bond_yield',        'Bond Yield'),
    ('daily_news',        'Daily News'),
    ('earnings_reminder', 'Earnings Reminder'),
    ('ipo_scout',         'IPO Scout'),
    ('price_alerts',      'Price Alerts'),
]

def build_benchmark_section() -> tuple[str, str]:
    """Reads last benchmark_scores.json record and formats as email section."""
    if not cfg.get('openai_api_key', ''):
        return '', ''
    scores_file = BASE / 'state' / 'benchmark_scores.json'
    if not scores_file.exists():
        return '', ''
    try:
        records = json.loads(scores_file.read_text(encoding='utf-8'))
        if not records:
            return '', ''
        last    = records[-1]
        ts      = last.get('timestamp', '')
        agents  = last.get('agents', {})
    except Exception:
        return '', ''

    def score_badge(s: float) -> str:
        if s >= 4.0:
            color, bg = '#166534', '#dcfce7'
        elif s >= 3.0:
            color, bg = '#92400e', '#fef3c7'
        else:
            color, bg = '#991b1b', '#fee2e2'
        return (f'<span style="background:{bg};color:{color};font-weight:700;'
                f'padding:2px 8px;border-radius:12px;font-size:13px">{s:.1f}</span>')

    th = 'padding:6px 10px;text-align:center;font-size:12px;color:#6b7280;font-weight:600'
    header_cells = (f'<th style="{th};text-align:left">Agent</th>'
                    f'<th style="{th}">Overall</th>'
                    + ''.join(f'<th style="{th}">{lbl}</th>' for lbl in _BENCHMARK_LABELS)
                    + f'<th style="{th};text-align:left">Summary</th>')

    rows_html  = ''
    rows_plain = ''
    for key, label in _BENCHMARK_AGENTS:
        if key not in agents:
            continue
        res     = agents[key]
        overall = res.get('overall', 0)
        scores  = res.get('scores', {})
        summary = res.get('summary', '')
        dim_cells = ''.join(
            f'<td style="padding:6px 10px;text-align:center;font-size:13px">'
            f'{scores.get(d, "—")}</td>'
            for d in _BENCHMARK_DIMS
        )
        rows_html += (
            f'<tr style="border-bottom:1px solid #e0e7ff">'
            f'<td style="padding:8px 10px;font-weight:600;font-size:14px">{label}</td>'
            f'<td style="padding:6px 10px;text-align:center">{score_badge(overall)}</td>'
            f'{dim_cells}'
            f'<td style="padding:6px 12px;font-size:12px;color:#6b7280">{summary}</td>'
            f'</tr>'
        )
        star = '🟢' if overall >= 4.0 else ('🟡' if overall >= 3.0 else '🔴')
        rows_plain += f'  {star} {label:<22} {overall:.1f}  {summary}\n'

    ts_fmt = ts[:16].replace('T', ' ') if ts else 'unknown'
    html = (
        f'<div style="background:#eef2ff;border-radius:8px;padding:10px 14px;margin-bottom:12px">'
        f'<p style="margin:0;font-size:12px;color:#4338ca">Scored by Claude Haiku · '
        f'Last run: {ts_fmt} · 5 dimensions (1–5 each)</p></div>'
        f'<table style="border-collapse:collapse;width:100%">'
        f'<tr style="background:#eef2ff">{header_cells}</tr>'
        + rows_html + '</table>'
    )
    plain = rows_plain
    return html, plain

# ─────────────────────────────────────────────────────────────────────────────
# Build & Send Email
# ─────────────────────────────────────────────────────────────────────────────
SECTION_STYLE = 'margin:24px 0 8px;padding:10px 16px;border-left:4px solid {color};background:{bg};font-size:16px;font-weight:700'

def build_email() -> tuple[str, str]:
    """Returns (html_body, plain_body)."""
    today_str = datetime.now().strftime('%A, %B %d %Y')

    news_html,     news_plain     = build_news_section()
    bond_html,     bond_plain     = build_bond_section()
    earnings_html, earnings_plain = build_earnings_section()
    price_html,    price_plain    = build_price_section()
    stock_html,    stock_plain    = build_stock_summary_section()
    ipo_html,      ipo_plain      = build_ipo_section()
    bench_html,    bench_plain    = build_benchmark_section()

    # ── Plain text ────────────────────────────────────────────────────────────
    plain = f'DAILY INVESTMENT REPORT — {today_str}\n{"="*60}\n\n'
    plain += '1. STOCK MARKET NEWS\n' + ('-'*40) + '\n' + news_plain + '\n'
    plain += '2. 10-YEAR TREASURY YIELD\n' + ('-'*40) + '\n' + bond_plain + '\n'
    plain += '3. UPCOMING EARNINGS (NEXT 7 DAYS)\n' + ('-'*40) + '\n' + earnings_plain + '\n'
    _n = 4
    if price_plain:
        plain += f'{_n}. PRICE ALERTS — ALAB & GARTNER\n' + ('-'*40) + '\n' + price_plain + '\n'
        _n += 1
    if stock_plain:
        plain += f'{_n}. STOCK NEWS SUMMARY — ALAB & GARTNER\n' + ('-'*40) + '\n' + stock_plain + '\n'
        _n += 1
    if ipo_plain:
        plain += f'{_n}. UPCOMING TECH IPOs\n' + ('-'*40) + '\n' + ipo_plain + '\n'
        _n += 1
    if bench_plain:
        plain += f'{_n}. AGENT BENCHMARK SCORECARD\n' + ('-'*40) + '\n' + bench_plain + '\n'

    # ── HTML ──────────────────────────────────────────────────────────────────
    def section(title, body, color, bg):
        return (
            f'<h2 style="{SECTION_STYLE.format(color=color, bg=bg)}">{title}</h2>'
            + body
        )

    body_parts = [
        section('📰 1. Stock Market News', news_html, '#3b82f6', '#eff6ff'),
        section('📈 2. 10-Year Treasury Yield', bond_html, '#f59e0b', '#fffbeb'),
        section('📅 3. Upcoming Earnings — Next 7 Days', earnings_html, '#8b5cf6', '#f5f3ff'),
    ]
    n = 4
    if price_html:
        body_parts.append(section(f'🚨 {n}. Price Alerts — ALAB & Gartner', price_html, '#ef4444', '#fef2f2'))
        n += 1
    if stock_html:
        body_parts.append(section(f'📰 {n}. Stock News — ALAB & Gartner', stock_html, '#f97316', '#fff7ed'))
        n += 1
    if ipo_html:
        body_parts.append(section(f'🔍 {n}. Upcoming Tech IPOs', ipo_html, '#10b981', '#f0fdf4'))
        n += 1
    if bench_html:
        body_parts.append(section(f'🤖 {n}. Agent Benchmark Scorecard', bench_html, '#6366f1', '#eef2ff'))

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#1f2937">
  <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb);padding:24px 28px;border-radius:12px;margin-bottom:24px">
    <h1 style="margin:0;color:#fff;font-size:22px">📊 Daily Investment Report</h1>
    <p style="margin:6px 0 0;color:#bfdbfe;font-size:14px">{today_str}</p>
  </div>
  {''.join(body_parts)}
  <div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:12px">
    Generated by your Investment Agents · Data: yfinance, stockanalysis.com, Groq AI
  </div>
</body></html>"""

    return html, plain

def send_email(subject: str, html_body: str, plain_body: str):
    smtp_host = cfg.get('smtp_host', 'smtp.gmail.com')
    smtp_port = int(cfg.get('smtp_port', 587))
    sender    = cfg.get('sender_email', '')
    password  = cfg.get('sender_password', '')
    recipient = cfg.get('recipient_email', '')

    if not all([sender, password, recipient]):
        print('  ✗ Email config incomplete. Fill in config/email_config.json')
        print('  Plain text report:\n')
        print(plain_body)
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = sender
    msg['To']      = recipient
    msg.attach(MIMEText(plain_body, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body,  'html',  'utf-8'))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f'  ✅ Email sent to {recipient}')

def main():
    print(f'\n{"="*60}')
    print(f'  DAILY INVESTMENT REPORT')
    print(f'  {datetime.now().strftime("%A, %B %d %Y  %H:%M")}')
    print(f'{"="*60}\n')

    print('  Building report sections...')
    html_body, plain_body = build_email()

    subject = f'📊 Investment Report — {datetime.now().strftime("%b %d, %Y")}'
    print(f'  Sending: {subject}')
    send_email(subject, html_body, plain_body)

if __name__ == '__main__':
    main()
