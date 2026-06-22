import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

TICKERS = {
    "SOX":       ("^SOX",   "SOX（フィラデルフィア半導体）"),
    "DOW":       ("^DJI",   "NYダウ"),
    "DOW_F":     ("YM=F",   "NYダウ先物"),
    "NDX":       ("^NDX",   "ナスダック100"),
    "NDX_F":     ("NQ=F",   "ナスダック100先物"),
    "N225":      ("^N225",  "日経平均"),
    "N225_F":    ("NKD=F",  "日経先物（ドル建て）"),
    "VIX":       ("^VIX",   "VIX（恐怖指数）"),
    "NKVIX":     ("^VXJ",   "日経VI"),
}


def vix_level(value):
    if value < 15:
        return "✅ 低恐怖（安定）"
    elif value < 20:
        return "🟢 通常"
    elif value < 25:
        return "🟡 やや警戒"
    elif value < 30:
        return "🟠 警戒"
    elif value < 40:
        return "🔴 高警戒"
    else:
        return "🚨 極度の恐怖・危機"


def nkvix_level(value):
    if value < 20:
        return "✅ 低恐怖（安定）"
    elif value < 25:
        return "🟢 通常"
    elif value < 30:
        return "🟡 やや警戒"
    elif value < 40:
        return "🔴 警戒"
    else:
        return "🚨 高警戒・危機"


def fetch(symbol):
    try:
        hist = yf.Ticker(symbol).history(period="5d")
        if len(hist) < 1:
            return None
        latest = hist.iloc[-1]
        close = latest["Close"]
        date = hist.index[-1].strftime("%Y-%m-%d")
        if len(hist) >= 2:
            prev = hist.iloc[-2]["Close"]
            change = close - prev
            change_pct = (change / prev) * 100
        else:
            change = 0.0
            change_pct = 0.0
        return {"close": close, "change": change, "pct": change_pct, "date": date}
    except Exception:
        return None


def format_row(label, data, decimals=2):
    if data is None:
        return f"  {label:<28} データ取得失敗\n"
    sign = "+" if data["change"] >= 0 else ""
    direction = "▲" if data["change"] >= 0 else "▼"
    return (
        f"  {label:<28} {data['close']:>10,.{decimals}f}  "
        f"{direction}{abs(data['pct']):.2f}%  ({sign}{data['change']:,.{decimals}f})\n"
    )


def build_body(results, now):
    sox = results["SOX"]
    latest_date = sox["date"] if sox else "N/A"

    body = f"""朝の市場レポート

取引日:   {latest_date}
送信日時: {now.strftime("%Y年%m月%d日 %H時%M分")} (JST)

{'='*60}
【米国市場】
{'='*60}
{format_row("SOX（フィラデルフィア半導体）", results["SOX"])}\
{format_row("NYダウ", results["DOW"])}\
{format_row("NYダウ先物", results["DOW_F"])}\
{format_row("ナスダック100", results["NDX"])}\
{format_row("ナスダック100先物", results["NDX_F"])}
{'='*60}
【日本市場】
{'='*60}
{format_row("日経平均", results["N225"])}\
{format_row("日経先物（ドル建て）", results["N225_F"])}
{'='*60}
【恐怖指数（ボラティリティ）】
{'='*60}
"""

    vix = results["VIX"]
    nkvix = results["NKVIX"]

    if vix:
        body += (
            f"  VIX（恐怖指数）\n"
            f"    現在値: {vix['close']:.2f}\n"
            f"    判定:   {vix_level(vix['close'])}\n"
            f"    前日比: {'+' if vix['change'] >= 0 else ''}{vix['change']:.2f}  ({'+' if vix['pct'] >= 0 else ''}{vix['pct']:.2f}%)\n\n"
            f"  [VIX 目安]\n"
            f"    < 15 : ✅ 低恐怖（安定）\n"
            f"    15-20: 🟢 通常\n"
            f"    20-25: 🟡 やや警戒\n"
            f"    25-30: 🟠 警戒\n"
            f"    30-40: 🔴 高警戒\n"
            f"    > 40 : 🚨 極度の恐怖・危機\n\n"
        )
    else:
        body += "  VIX: データ取得失敗\n\n"

    if nkvix:
        body += (
            f"  日経VI\n"
            f"    現在値: {nkvix['close']:.2f}\n"
            f"    判定:   {nkvix_level(nkvix['close'])}\n"
            f"    前日比: {'+' if nkvix['change'] >= 0 else ''}{nkvix['change']:.2f}  ({'+' if nkvix['pct'] >= 0 else ''}{nkvix['pct']:.2f}%)\n\n"
            f"  [日経VI 目安]\n"
            f"    < 20 : ✅ 低恐怖（安定）\n"
            f"    20-25: 🟢 通常\n"
            f"    25-30: 🟡 やや警戒\n"
            f"    30-40: 🔴 警戒\n"
            f"    > 40 : 🚨 高警戒・危機\n"
        )
    else:
        body += "  日経VI: データ取得失敗\n"

    return body


def send_email(results, now):
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    to_email = os.environ["TO_EMAIL"]

    sox = results["SOX"]
    if sox:
        direction = "▲" if sox["change"] >= 0 else "▼"
        subject = (
            f"【朝の市場レポート】{sox['date']} "
            f"SOX {sox['close']:,.2f} {direction}{abs(sox['pct']):.2f}%"
        )
    else:
        subject = f"【朝の市場レポート】{now.strftime('%Y-%m-%d')}"

    body = build_body(results, now)

    msg = MIMEMultipart()
    msg["From"] = gmail_address
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_password)
        server.send_message(msg)

    print(f"送信完了: {subject}")


if __name__ == "__main__":
    now = datetime.now(JST)
    results = {key: fetch(symbol) for key, (symbol, _) in TICKERS.items()}
    send_email(results, now)
