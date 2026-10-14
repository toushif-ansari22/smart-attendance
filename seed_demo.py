import sqlite3
from datetime import datetime, timedelta

MY_EMAIL = "demo@example.com"   # sab demo students ki email yehi, taaki galti se kisi aur ko mail na jaye

conn = sqlite3.connect("demo.db")
cur = conn.cursor()
cur.execute("DROP TABLE IF EXISTS attendance")
cur.execute("DROP TABLE IF EXISTS students")
cur.execute("CREATE TABLE students (roll_no TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT)")
cur.execute("""CREATE TABLE attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no TEXT NOT NULL, date TEXT NOT NULL, time TEXT NOT NULL,
    UNIQUE(roll_no, date))""")

# pichle 24 din (Sunday chhodke) = class days
days = []
d = 0
while len(days) < 20:
    day = datetime.now() - timedelta(days=d)
    d += 1
    if day.weekday() != 6:
        days.append(day.strftime("%Y-%m-%d"))

# (roll, naam, attendance fraction)
demo = [("101", "Toushif", 0.95), ("102", "Rahul", 0.80),
        ("103", "Amit", 0.60), ("104", "Sana", 0.90), ("105", "Vikas", 0.45)]

for roll, name, frac in demo:
    cur.execute("INSERT INTO students VALUES (?, ?, ?)", (roll, name, MY_EMAIL))
    present = round(frac * len(days))
    for day in days[:present]:
        cur.execute("INSERT INTO attendance (roll_no, date, time) VALUES (?, ?, ?)",
                    (roll, day, "09:15:00"))

conn.commit()
conn.close()
print("demo.db ban gayi (20 class days, 5 students)")

