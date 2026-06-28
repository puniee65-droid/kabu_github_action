import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

TICKERS = {
    "SOX":    ("^SOX",   "SOX（フィラデルフィア半導体）"),
    "DOW":    ("^DJI",   "NYダウ"),
    "DOW_F":  ("YM=F",   "NYダウ先物"),
    "NDX":    ("^IXIC",  "ナスダック総合"),
    "NDX_F":  ("NQ=F",   "ナスダック先物(NQ100)"),
    "N225":   ("^N225",  "日経平均"),
    "N225_F": ("NKD=F",  "日経先物（ドル建て）"),
    "VIX":    ("^VIX",   "VIX（恐怖指数）"),
    "NKVIX":  ("^VXJ",   "日経VI"),
}

VIX_GUIDE = """\
  [VIX 目安]
    < 15 : ✅ 低恐怖（安定）
    15-20: 🟢 通常
    20-25: 🟡 やや警戒
    25-30: 🟠 警戒
    30-40: 🔴 高警戒
    > 40 : 🚨 極度の恐怖・危機"""

NKVIX_GUIDE = """\
  [日経VI 目安]
    < 20 : ✅ 低恐怖（安定）
    20-25: 🟢 通常
    25-30: 🟡 やや警戒
    30-40: 🔴 警戒
    > 40 : 🚨 高警戒・危機"""


def vix_level(value):
    if value < 15:   return "✅ 低恐怖（安定）"
    elif value < 20: return "🟢 通常"
    elif value < 25: return "🟡 やや警戒"
    elif value < 30: return "🟠 警戒"
    elif value < 40: return "🔴 高警戒"
    else:            return "🚨 極度の恐怖・危機"


def nkvix_level(value):
    if value < 20:   return "✅ 低恐怖（安定）"
    elif value < 25: return "🟢 通常"
    elif value < 30: return "🟡 やや警戒"
    elif value < 40: return "🔴 警戒"
    else:            return "🚨 高警戒・危機"


def get_crumb(session):
    # 方法1: Cookie なしで直接取得
    try:
        r = session.get(
            'https://query1.finance.yahoo.com/v1/test/getcrumb',
            headers={'User-Agent': UA, 'Accept': '*/*'},
            timeout=10,
        )
        text = r.text.strip()
        if r.ok and text and len(text) < 50 and '<' not in text and '{' not in text:
            return text
    except Exception:
        pass

    # 方法2: finance.yahoo.com でセッション確立 → crumb
    session.get('https://finance.yahoo.com/',
                headers={'User-Agent': UA, 'Accept': 'text/html'}, timeout=15)
    r = session.get(
        'https://query2.finance.yahoo.com/v1/test/getcrumb',
        headers={'User-Agent': UA, 'Accept': '*/*'},
        timeout=10,
    )
    if r.ok and r.text.strip():
        return r.text.strip()
    raise RuntimeError(f"crumb取得失敗 (HTTP {r.status_code})")


def fetch(session, crumb, symbol):
    url = (
        f'https://query1.finance.yahoo.com/v8/finance/chart/'
        f'{requests.utils.quote(symbol)}'
        f'?interval=60m&range=60d'
        f'&crumb={requests.utils.quote(crumb)}'
        f'&includePrePost=false'
    )
    try:
        r = session.get(url, headers={
            'User-Agent': UA,
            'Accept': 'application/json',
            'Referer': 'https://finance.yahoo.com/',
        }, timeout=15)
        if not r.ok:
            print(f"  {symbol}: HTTP {r.status_code}")
            return None
        j = r.json()
        if j.get('chart', {}).get('error') or not j.get('chart', {}).get('result'):
            return None

        meta = j['chart']['result'][0].get('meta', {})
        current    = meta.get('regularMarketPrice')
        prev_close = meta.get('previousClose') or meta.get('chartPreviousClose')
        ts         = meta.get('regularMarketTime')
        date_str   = (datetime.fromtimestamp(ts, tz=JST).strftime('%Y-%m-%d')
                      if ts else 'N/A')

        if current is None or prev_close is None or prev_close == 0:
            return None

        change = current - prev_close
        pct    = (change / prev_close) * 100
        return {'close': current, 'change': change, 'pct': pct, 'date': date_str}

    except Exception as e:
        print(f"  {symbol}: {e}")
        return None


def format_row(label, data, decimals=2):
    if data is None:
        return f"  {label:<28} データ取得失敗\n"
    sign      = "+" if data["change"] >= 0 else ""
    direction = "▲" if data["change"] >= 0 else "▼"
    return (
        f"  {label:<28} {data['close']:>10,.{decimals}f}"
        f"  ({direction}{abs(data['pct']):.2f}%  {sign}{data['change']:,.{decimals}f})\n"
    )


def format_vi_row(label, data, level_fn):
    if data is None:
        return f"  {label:<16} データ取得失敗\n"
    sign      = "+" if data["change"] >= 0 else ""
    direction = "▲" if data["change"] >= 0 else "▼"
    judgment  = level_fn(data["close"])
    return (
        f"  {label:<16} {data['close']:>6.2f}"
        f"  ({direction}{abs(data['pct']):.2f}%  {sign}{data['change']:.2f})"
        f"  {judgment}\n"
    )


def build_body(results, now):
    sox        = results["SOX"]
    latest_date = sox["date"] if sox else "N/A"
    sep         = "=" * 60

    body = f"""朝の市場レポート

取引日:   {latest_date}
送信日時: {now.strftime("%Y年%m月%d日 %H時%M分")} (JST)

{sep}
【米国市場】
{sep}
{format_row("SOX（フィラデルフィア半導体）", results["SOX"])}\
{format_row("NYダウ", results["DOW"])}\
{format_row("NYダウ先物", results["DOW_F"])}\
{format_row("ナスダック総合", results["NDX"])}\
{format_row("ナスダック先物(NQ100)", results["NDX_F"])}
{sep}
【日本市場】
{sep}
{format_row("日経平均", results["N225"])}\
{format_row("日経先物（ドル建て）", results["N225_F"])}
{sep}
【恐怖指数（ボラティリティ）】
{sep}
{format_vi_row("VIX（恐怖指数）", results["VIX"], vix_level)}\
{format_vi_row("日経VI", results["NKVIX"], nkvix_level)}
{sep}
【VIX / 日経VI 基準値】
{sep}
{VIX_GUIDE}

{NKVIX_GUIDE}
"""
    return body


def send_email(results, now):
    gmail_address  = os.environ["GMAIL_ADDRESS"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    to_email       = os.environ["TO_EMAIL"]

    sox = results["SOX"]
    if sox:
        direction = "▲" if sox["change"] >= 0 else "▼"
        subject   = (f"【朝の市場レポート】{sox['date']} "
                     f"SOX {sox['close']:,.2f} {direction}{abs(sox['pct']):.2f}%")
    else:
        subject = f"【朝の市場レポート】{now.strftime('%Y-%m-%d')}"

    body = build_body(results, now)

    msg = MIMEMultipart()
    msg["From"]    = gmail_address
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_password)
        server.send_message(msg)

    print(f"送信完了: {subject}")


if __name__ == "__main__":
    now     = datetime.now(JST)
    session = requests.Session()
    crumb   = get_crumb(session)
    print(f"crumb取得: {crumb[:8]}...")
    results = {key: fetch(session, crumb, symbol)
               for key, (symbol, _) in TICKERS.items()}
    send_email(results, now)
