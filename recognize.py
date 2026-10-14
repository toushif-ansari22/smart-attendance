import cv2
import pickle
import sqlite3
import numpy as np
import face_recognition
from datetime import datetime

SCALE = 0.5
TOLERANCE = 0.5
DB = "attendance.db"

with open("encodings.pickle", "rb") as f:
    data = pickle.load(f)
known_encodings = data["encodings"]
known_labels = data["names"]
print(f"{len(known_encodings)} encodings load hui")

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS students (
    roll_no TEXT PRIMARY KEY,
    name TEXT NOT NULL)""")
cur.execute("""CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    UNIQUE(roll_no, date))""")

for label in set(known_labels):
    roll, name = label.split("|", 1)
    cur.execute("INSERT OR IGNORE INTO students VALUES (?, ?)", (roll, name))
conn.commit()


def mark_attendance(roll):
    now = datetime.now()
    cur.execute(
        "INSERT OR IGNORE INTO attendance (roll_no, date, time) VALUES (?, ?, ?)",
        (roll, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")))
    conn.commit()
    return cur.rowcount == 1


cam = cv2.VideoCapture(0)
if not cam.isOpened():
    print("Camera nahi khula. Camera permission check karo.")
    raise SystemExit

print("Q dabao band karne ke liye")
results = []
frame_no = 0

while True:
    ok, frame = cam.read()
    if not ok:
        break
    frame_no += 1

    if frame_no % 2 == 0:
        small = cv2.resize(frame, (0, 0), fx=SCALE, fy=SCALE)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb)
        encs = face_recognition.face_encodings(rgb, locs)

        results = []
        for box, enc in zip(locs, encs):
            text, color = "Unknown", (0, 0, 255)
            if known_encodings:
                dists = face_recognition.face_distance(known_encodings, enc)
                best = int(np.argmin(dists))
                if dists[best] <= TOLERANCE:
                    roll, name = known_labels[best].split("|", 1)
                    if mark_attendance(roll):
                        print(f"[MARKED] {roll} - {name} - {datetime.now():%H:%M:%S}")
                        text = f"{name} - MARKED"
                    else:
                        text = f"{name} - Already marked"
                    color = (0, 255, 0)
            top, right, bottom, left = [int(v / SCALE) for v in box]
            results.append(((top, right, bottom, left), text, color))

    for (top, right, bottom, left), text, color in results:
        cv2.rectangle(frame, (left, top), (right, bottom), color, 3)
        cv2.putText(frame, text, (left, max(top - 12, 25)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

    cv2.imshow("Smart Attendance", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cam.release()
cv2.destroyAllWindows()
conn.close()
