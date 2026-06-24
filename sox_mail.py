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
    "NDX":       ("^IXIC",  "ナスダック総合"),
    "NDX_F":     ("NQ=F",   "ナスダック先物(NQ100)"),
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
        hist = yf.Ticker(symbol).history(period="10d")
        hist = hist[hist["Volume"] > 0]  # Volume=0 の未完了エントリを除外
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
        f"  {label:<28} {data['close']:>10,.{decimals}f}"
        f"  ({direction}{abs(data['pct']):.2f}%  {sign}{data['change']:,.{decimals}f})\n"
    )


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


def format_vi_row(label, data, level_fn):
    if data is None:
        return f"  {label:<16} データ取得失敗\n"
    sign = "+" if data["change"] >= 0 else ""
    direction = "▲" if data["change"] >= 0 else "▼"
    judgment = level_fn(data["close"])
    return (
        f"  {label:<16} {data['close']:>6.2f}"
        f"  ({direction}{abs(data['pct']):.2f}%  {sign}{data['change']:.2f})"
        f"  {judgment}\n"
    )


def build_body(results, now):
    sox = results["SOX"]
    latest_date = sox["date"] if sox else "N/A"

    sep = "=" * 60

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
