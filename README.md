# Smart Attendance System

Face-recognition based classroom attendance with blink-based anti-spoofing, a Streamlit dashboard and automatic low-attendance email alerts.

Built as a diploma minor project (Computer Engineering).

## Features

- **Face recognition attendance**: webcam identifies students and marks attendance in SQLite (one entry per student per day).
- **Anti-spoofing (liveness check)**: attendance is marked only after 2 clear eye blinks, so a photo shown on a phone does not work.
- **Dashboard**: student-wise attendance %, date-wise present list, and a low-attendance list (default threshold 75%).
- **Email alerts**: students below the threshold get an automatic email (Gmail SMTP).

## How it works

```
Webcam -> face detection -> face encoding (128-d) -> match with registered students
       -> blink check (2 blinks in 8 s) -> SQLite attendance table
       -> Streamlit dashboard + email alert for low attendance
```

**Blink detection:** the Eye Aspect Ratio (EAR) is computed from eye landmarks. An eye counts as closed when it drops well below that person's own normal eye height (relative drop), both eyes close together, and the closure lasts 2 to 10 frames. Two such blinks within 8 seconds are required.

## Tech stack

Python, OpenCV, face_recognition (dlib), NumPy, pandas, SQLite, Streamlit, smtplib.

## Project structure

| File | Purpose |
|---|---|
| `register.py` | Capture 10 photos of a student from the webcam |
| `encode.py` | Build face encodings from the `dataset/` folder |
| `recognize.py` | Basic live attendance (no liveness check) |
| `recognize_blink3.py` | Live attendance with blink anti-spoofing (recommended) |
| `dashboard.py` | Streamlit dashboard |
| `alert.py` | Low-attendance email alerts |
| `seed_demo.py` | Creates `demo.db` with fake data for testing the dashboard and alerts |

## Setup (macOS)

```bash
git clone https://github.com/toushif-ansari22/smart-attendance.git
cd smart-attendance

brew install cmake
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`dlib` takes a few minutes to compile on the first install.

## Usage

1. **Register a student** (allow camera access for Terminal when macOS asks):
   ```bash
   python register.py
   ```
   Enter roll number and name, then press SPACE when the green box appears. Repeat for each student.

2. **Build encodings** (run again whenever you add students):
   ```bash
   python encode.py
   ```

3. **Take attendance**:
   ```bash
   python recognize_blink3.py
   ```
   Face the camera and blink twice clearly. Press `Q` to quit.

4. **Open the dashboard**:
   ```bash
   streamlit run dashboard.py
   ```
   To try it with fake data: `python seed_demo.py`, then type `demo.db` in the sidebar "Database file" box.

5. **Send low-attendance emails** (Gmail App Password required):
   ```bash
   export ALERT_EMAIL="you@gmail.com"
   read -s "ALERT_APP_PASS?Password: "
   export ALERT_APP_PASS
   python alert.py            # dry run, nothing is sent
   python alert.py --send     # sends emails
   ```
   Add each student's email in the `students.email` column first. Never commit the app password.

## Limitations

- A **video replay** of a person blinking on a screen may still pass the blink check. A depth camera or head-turn challenge would be needed to stop this.
- Recognition accuracy depends on lighting and on the quality of registration photos.

## Future scope

- Random head-turn challenge for stronger liveness detection
- Multi-camera support and a web-based registration page
- Parent notification through SMS or WhatsApp
- Monthly PDF/Excel attendance reports

## Privacy

Student photos (`dataset/`), face encodings (`encodings.pickle`) and attendance databases (`*.db`) are not stored in this repository.

## Author

Toushif Ansari, Diploma in Computer Engineering, University Polytechnic, BIT Mesra.
