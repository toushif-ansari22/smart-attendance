import os
import smtplib
import sqlite3
import sys
from email.message import EmailMessage

import pandas as pd

DB = os.environ.get("ATT_DB", "attendance.db")
THRESHOLD = 75
SENDER = os.environ.get("ALERT_EMAIL")
APP_PASSWORD = os.environ.get("ALERT_APP_PASS")
SEND = "--send" in sys.argv   # --send ke bina email nahi jayegi (dry run)

conn = sqlite3.connect(DB)
students = pd.read_sql("SELECT roll_no, name, email FROM students", conn)
att = pd.read_sql("SELECT roll_no, date FROM attendance", conn)
conn.close()

total_days = att["date"].nunique()
if total_days == 0:
    print("Abhi koi attendance data nahi hai.")
    sys.exit()

counts = att.groupby("roll_no")["date"].nunique().rename("days_present")
df = students.merge(counts, on="roll_no", how="left")
df["days_present"] = df["days_present"].fillna(0).astype(int)
df["percentage"] = (df["days_present"] / total_days * 100).round(1)
low = df[df["percentage"] < THRESHOLD]

print(f"Total class days: {total_days}")
print(f"{THRESHOLD}% se kam attendance wale: {len(low)}")

if low.empty:
    print("Kisi ko alert bhejne ki zarurat nahi.")
    sys.exit()

if SEND:
    if not SENDER or not APP_PASSWORD:
        print("ALERT_EMAIL aur ALERT_APP_PASS set nahi hain.")
        sys.exit()
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(SENDER, APP_PASSWORD)

for _, row in low.iterrows():
    body = (f"Hello {row['name']},\n\n"
            f"Aapki attendance {row['percentage']}% hai "
            f"({row['days_present']}/{total_days} din). "
            f"Minimum {THRESHOLD}% zaruri hai. Kripya class regular attend karein.\n")
    if not SEND:
        print(f"[DRY RUN] {row['name']} ({row['email']}) -> {row['percentage']}%")
        continue
    if not row["email"]:
        print(f"{row['name']}: email nahi hai, skip")
        continue
    msg = EmailMessage()
    msg["Subject"] = "Low Attendance Alert"
    msg["From"] = SENDER
    msg["To"] = row["email"]
    msg.set_content(body)
    server.send_message(msg)
    print(f"Email bheji: {row['name']} ({row['email']})")

if SEND:
    server.quit()
