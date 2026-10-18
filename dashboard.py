import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

import integrity

st.set_page_config(page_title="Smart Attendance", layout="wide")
st.title("Smart Attendance Dashboard")

db = st.sidebar.text_input("Database file", "attendance.db")
threshold = st.sidebar.slider("Minimum attendance %", 50, 100, 75)

if not os.path.exists(db):
    st.error(f"{db} nahi mili. Pehle recognize_blink3.py chalao.")
    st.stop()

conn = sqlite3.connect(db)
students = pd.read_sql("SELECT roll_no, name FROM students", conn)
cols = [r[1] for r in conn.execute("PRAGMA table_info(attendance)").fetchall()]
extra = ", confidence, blinks, entry_hash" if "entry_hash" in cols else ""
att = pd.read_sql(f"SELECT id, roll_no, date, time{extra} FROM attendance ORDER BY id", conn)
check = integrity.verify(conn)
conn.close()

if att.empty:
    st.info("Abhi tak koi attendance nahi lagi hai.")
    st.stop()

total_days = att["date"].nunique()
counts = att.groupby("roll_no")["date"].nunique().rename("days_present")

summary = students.merge(counts, on="roll_no", how="left")
summary["days_present"] = summary["days_present"].fillna(0).astype(int)
summary["percentage"] = (summary["days_present"] / total_days * 100).round(1)
summary["status"] = summary["percentage"].apply(
    lambda p: "LOW" if p < threshold else "OK")

today = datetime.now().strftime("%Y-%m-%d")
present_today = att[att["date"] == today]["roll_no"].nunique()
low = summary[summary["status"] == "LOW"]

label = {"ok": "OK", "broken": "BROKEN", "unsealed": "NOT SEALED", "empty": "EMPTY"}
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total students", len(students))
c2.metric("Class days", total_days)
c3.metric("Present today", present_today)
c4.metric(f"Below {threshold}%", len(low))
c5.metric("Log integrity", label.get(check["status"], check["status"]))

tab1, tab2, tab3, tab4 = st.tabs(
    ["Student-wise %", "Date-wise", "Low attendance", "Integrity"])

with tab1:
    st.subheader("Attendance percentage")
    st.bar_chart(summary.set_index("name")["percentage"])
    st.dataframe(summary, width='stretch', hide_index=True)

with tab2:
    st.subheader("Date-wise attendance")
    dates = sorted(att["date"].unique(), reverse=True)
    pick = st.selectbox("Date chuno", dates)
    day = att[att["date"] == pick].merge(students, on="roll_no", how="left")
    st.write(f"{len(day)} student present")
    show_cols = ["roll_no", "name", "time"]
    for c in ("confidence", "blinks"):
        if c in day.columns:
            show_cols.append(c)
    st.dataframe(day[show_cols], width='stretch', hide_index=True)

with tab3:
    st.subheader(f"{threshold}% se kam attendance wale students")
    if low.empty:
        st.success("Sabki attendance theek hai.")
    else:
        st.dataframe(low[["roll_no", "name", "days_present", "percentage"]],
                     width='stretch', hide_index=True)

with tab4:
    st.subheader("Tamper-proof attendance log")
    if check["status"] == "ok":
        st.success(f"Integrity OK. {check['message']}")
    elif check["status"] == "broken":
        st.error(f"TAMPERING DETECTED. {check['message']}")
    else:
        st.warning(check["message"])
    st.caption(
        "Every record stores an HMAC-SHA256 hash that includes the previous "
        "record's hash. Changing or deleting any record breaks the chain after it.")
    if "entry_hash" in att.columns:
        latest = att.tail(10).iloc[::-1].copy()
        latest["entry_hash"] = latest["entry_hash"].str[:12]
        st.dataframe(latest, width='stretch', hide_index=True)
