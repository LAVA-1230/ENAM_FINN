"""Scout: pick the portfolio that gives the richest demo from real recent filings.

Fetches the last 30 days of NSE announcements and 1 month of prices for ~45
liquid names, and prints what each one would show (results, KMP change, rating,
pledge, big moves). Run: python scripts/scout.py
"""
import json
import re
import time
from datetime import date, timedelta

import httpx

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
}
CANDIDATES = """HDFCBANK ICICIBANK BAJFINANCE INFY TCS SUNPHARMA DRREDDY HINDUNILVR ITC NESTLEIND
MARUTI M&M LT ULTRACEMCO TITAN ASIANPAINT AXISBANK KOTAKBANK SBIN HCLTECH WIPRO TECHM CIPLA LUPIN
TATAMOTORS EICHERMOT BAJAJ-AUTO HEROMOTOCO TATASTEEL JSWSTEEL HINDALCO RELIANCE ONGC NTPC POWERGRID
ADANIENT DMART TRENT DIVISLAB APOLLOHOSP DIXON POLYCAB PERSISTENT COFORGE ZYDUSLIFE HAVELLS PIDILITIND
VOLTAS DABUR GODREJCP BRITANNIA INDIGO IRCTC""".split()

PAT = {
    "results": r"financial result|outcome of board meeting|integrated filing",
    "kmp": r"resignation|cessation|appointment|key managerial|change in director",
    "rating": r"credit rating|rating",
    "pledge": r"pledge|encumbrance|regulation 31|sast",
    "mna": r"acquisition|amalgamation|merger|scheme of arrangement",
    "order": r"order|letter of award|contract",
}


def main():
    c = httpx.Client(headers=H, timeout=30, follow_redirects=True)
    to, fr = date.today(), date.today() - timedelta(days=30)
    out = []
    for sym in CANDIDATES:
        try:
            r = c.get("https://www.nseindia.com/api/corporate-announcements",
                      params={"index": "equities", "symbol": sym,
                              "from_date": fr.strftime("%d-%m-%Y"), "to_date": to.strftime("%d-%m-%Y")})
            anns = r.json() if r.status_code == 200 else []
        except Exception:
            anns = []
        hits = {k: 0 for k in PAT}
        for a in anns:
            text = f"{a.get('desc', '')} {a.get('attchmntText', '')}".lower()
            for k, p in PAT.items():
                if re.search(p, text):
                    hits[k] += 1
        try:
            q = c.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym.replace('&', '%26')}.NS",
                      params={"range": "1mo", "interval": "1d"}).json()["chart"]["result"][0]
            closes = [x for x in q["indicators"]["quote"][0]["close"] if x]
            moves = [abs(b / a - 1) * 100 for a, b in zip(closes, closes[1:])]
            maxmove = round(max(moves), 1) if moves else 0
        except Exception:
            maxmove = None
        row = {"symbol": sym, "n": len(anns), "maxmove": maxmove, **hits}
        print(json.dumps(row))
        out.append(row)
        time.sleep(0.8)
    with open("scout_result.json", "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
