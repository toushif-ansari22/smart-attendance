import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Smart Attendance", layout="wide")
st.title("Smart Attendance Dashboard")

# ---- sidebar ----
db = st.sidebar.text_input("Database file", "attendance.db")
threshold = st.sidebar.slider("Minimum attendance %", 50, 100, 75)

if not os.path.exists(db):
    st.error(f"{db} nahi mili. Pehle recognize.py chalao.")
    st.stop()

# ---- data load ----
conn = sqlite3.connect(db)
students = pd.read_sql("SELECT roll_no, name FROM students", conn)
att = pd.read_sql("SELECT roll_no, date, time FROM attendance", conn)
conn.close()

if att.empty:
    st.info("Abhi tak koi attendance nahi lagi hai.")
    st.stop()

# ---- calculation ----
# jis din kam se kam ek student ki attendance lagi, wo class ka din maana gaya
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

# ---- top metrics ----
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total students", len(students))
c2.metric("Class days", total_days)
c3.metric("Present today", present_today)
c4.metric(f"Below {threshold}%", len(low))

tab1, tab2, tab3 = st.tabs(["Student-wise %", "Date-wise", "Low attendance"])

with tab1:
    st.subheader("Attendance percentage")
    st.bar_chart(summary.set_index("name")["percentage"])
    st.dataframe(summary, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Date-wise attendance")
    dates = sorted(att["date"].unique(), reverse=True)
    pick = st.selectbox("Date chuno", dates)
    day = att[att["date"] == pick].merge(students, on="roll_no", how="left")
    st.write(f"{len(day)} student present")
    st.dataframe(day[["roll_no", "name", "time"]],
                 use_container_width=True, hide_index=True)

with tab3:
    st.subheader(f"{threshold}% se kam attendance wale students")
    if low.empty:
        st.success("Sabki attendance theek hai.")
    else:
        st.dataframe(low[["roll_no", "name", "days_present", "percentage"]],
                     use_container_width=True, hide_index=True)
