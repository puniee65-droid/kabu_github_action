import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))


def get_sox_data():
    ticker = yf.Ticker("^SOX")
    hist = ticker.history(period="5d")

    if len(hist) < 2:
        raise ValueError("SOXデータが取得できませんでした")

    latest = hist.iloc[-1]
    prev = hist.iloc[-2]

    current_price = latest["Close"]
    prev_price = prev["Close"]
    change = current_price - prev_price
    change_pct = (change / prev_price) * 100
    latest_date = hist.index[-1].strftime("%Y-%m-%d")

    return current_price, change, change_pct, latest_date


def send_email(current_price, change, change_pct, latest_date):
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    to_email = os.environ["TO_EMAIL"]

    now = datetime.now(JST)
    sign = "+" if change >= 0 else ""
    direction = "▲" if change >= 0 else "▼"

    subject = f"【SOX指数】{latest_date} {current_price:,.2f} {direction}{abs(change_pct):.2f}%"

    body = f"""SOX指数（フィラデルフィア半導体指数）レポート

取引日:   {latest_date}
送信日時: {now.strftime("%Y年%m月%d日 %H時%M分")} (JST)

現在値:  {current_price:>10,.2f}
前日比:  {sign}{change:>10,.2f}  ({sign}{change_pct:.2f}%)
"""

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
    current_price, change, change_pct, latest_date = get_sox_data()
    send_email(current_price, change, change_pct, latest_date)
