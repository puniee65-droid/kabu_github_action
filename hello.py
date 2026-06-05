from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
now = datetime.now(JST)
filename = now.strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
content = now.strftime("%Y年%m月%d日 %H時%M分%S秒")

with open(filename, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Hello World - {content} を {filename} に書き込みました")
