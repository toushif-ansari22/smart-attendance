import cv2
import time
import pickle
import sqlite3
from collections import deque
import numpy as np
import face_recognition
from datetime import datetime

import integrity

SCALE = 0.5
TOLERANCE = 0.5
DROP_RATIO = 0.75      # aankh apni normal height se is ratio se kam ho to "band"
EAR_ABS_MAX = 0.26     # band maanne ke liye EAR is se neeche bhi hona chahiye
MIN_CLOSED = 2         # kam se kam itne frame band (1 frame ka jhatka reject)
MAX_CLOSED = 10        # isse zyada der band = blink nahi
REQUIRED_BLINKS = 2    # attendance ke liye itne blink chahiye
BLINK_WINDOW = 8       # in seconds ke andar
WARMUP = 8             # itne samples ke baad hi blink gino
HISTORY = 20
DB = "attendance.db"

with open("encodings.pickle", "rb") as f:
    data = pickle.load(f)
known_encodings = data["encodings"]
known_labels = data["names"]
print(f"{len(known_encodings)} encodings load hui")

conn = sqlite3.connect(DB)
integrity.ensure_schema(conn)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS students (
    roll_no TEXT PRIMARY KEY,
    name TEXT NOT NULL)""")
conn.commit()

check = integrity.verify(conn)
print(f"Integrity check: {check['status'].upper()} ({check['checked']} records)")
if check["status"] == "unsealed":
    print(check["message"])
    raise SystemExit
if check["status"] == "broken":
    print("WARNING: " + check["message"])


def already_marked(roll):
    today = datetime.now().strftime("%Y-%m-%d")
    cur.execute("SELECT 1 FROM attendance WHERE roll_no=? AND date=?", (roll, today))
    return cur.fetchone() is not None


def eye_ratio(eye):
    p = np.array(eye, dtype=float)
    a = np.linalg.norm(p[1] - p[5])
    b = np.linalg.norm(p[2] - p[4])
    c = np.linalg.norm(p[0] - p[3])
    return (a + b) / (2.0 * c) if c > 0 else 1.0


def new_state():
    return {"hl": deque(maxlen=HISTORY), "hr": deque(maxlen=HISTORY),
            "closed": 0, "blinks": []}


cam = cv2.VideoCapture(0)
if not cam.isOpened():
    print("Camera nahi khula. Camera permission check karo.")
    raise SystemExit

print(f"Attendance ke liye {REQUIRED_BLINKS} baar saaf palak jhapkao.")
print("Q dabao band karne ke liye")

results = []
state = {}
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
        marks = face_recognition.face_landmarks(rgb, locs)

        results = []
        for box, enc, lm in zip(locs, encs, marks):
            text, color, info = "Unknown", (0, 0, 255), ""

            if known_encodings:
                dists = face_recognition.face_distance(known_encodings, enc)
                best = int(np.argmin(dists))
                if dists[best] <= TOLERANCE:
                    roll, name = known_labels[best].split("|", 1)
                    st = state.setdefault(roll, new_state())

                    l = eye_ratio(lm["left_eye"])
                    r = eye_ratio(lm["right_eye"])
                    ear = (l + r) / 2.0

                    base_ear = None
                    closed = False
                    if len(st["hl"]) >= WARMUP and len(st["hr"]) >= WARMUP:
                        base_l = float(np.percentile(st["hl"], 80))
                        base_r = float(np.percentile(st["hr"], 80))
                        base_ear = (base_l + base_r) / 2.0
                        closed = (l < base_l * DROP_RATIO
                                  and r < base_r * DROP_RATIO
                                  and ear < EAR_ABS_MAX)

                    if closed:
                        st["closed"] += 1
                    else:
                        if MIN_CLOSED <= st["closed"] <= MAX_CLOSED:
                            st["blinks"].append(time.time())
                        st["closed"] = 0
                        st["hl"].append(l)
                        st["hr"].append(r)

                    now_t = time.time()
                    st["blinks"] = [t for t in st["blinks"] if now_t - t <= BLINK_WINDOW]
                    count = len(st["blinks"])

                    base_txt = f"{base_ear:.2f}" if base_ear else "..."
                    info = f"EAR {ear:.2f} base {base_txt} blinks {count}/{REQUIRED_BLINKS}"

                    if already_marked(roll):
                        text, color = f"{name} - Already marked", (0, 255, 0)
                    elif count >= REQUIRED_BLINKS:
                        score = 1.0 - float(dists[best])
                        if integrity.add_entry(conn, roll, score, count):
                            print(f"[MARKED] {roll} - {name} - {datetime.now():%H:%M:%S} "
                                  f"(match score {score:.2f}, blinks {count}, sealed)")
                        text, color = f"{name} - MARKED", (0, 255, 0)
                    else:
                        text = f"{name} - Palak jhapkao ({count}/{REQUIRED_BLINKS})"
                        color = (0, 255, 255)

            top, right_, bottom, left_ = [int(v / SCALE) for v in box]
            results.append(((top, right_, bottom, left_), text, color, info))

    for (top, right_, bottom, left_), text, color, info in results:
        cv2.rectangle(frame, (left_, top), (right_, bottom), color, 3)
        cv2.putText(frame, text, (left_, max(top - 12, 25)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        if info:
            cv2.putText(frame, info, (left_, bottom + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    cv2.imshow("Smart Attendance (Blink v3 + Integrity)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cam.release()
cv2.destroyAllWindows()
conn.close()
