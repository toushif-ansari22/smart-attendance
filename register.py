import cv2
import os
import face_recognition

TARGET = 10          # kitni photos leni hain
SCALE = 0.25         # detection ke liye frame chhota karte hain (bade face fix)

roll = input("Roll number: ").strip()
name = input("Student name: ").strip().replace(" ", "_")

folder = f"dataset/{roll}_{name}"
os.makedirs(folder, exist_ok=True)

cam = cv2.VideoCapture(0)
if not cam.isOpened():
    print("Camera nahi khula. Camera permission check karo.")
    raise SystemExit

count = len([f for f in os.listdir(folder) if f.endswith(".jpg")])
print("SPACE = photo lo | Q = band karo")
print("Green box dikhe tabhi SPACE dabao. Sir thoda ghumate raho.")

while count < TARGET:
    ok, frame = cam.read()
    if not ok:
        print("Frame nahi mila")
        break

    # chhota frame banake face dhundo
    small = cv2.resize(frame, (0, 0), fx=SCALE, fy=SCALE)
    rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    faces = face_recognition.face_locations(rgb_small)

    # live preview pe green box dikhao
    show = frame.copy()
    for (top, right, bottom, left) in faces:
        top, right, bottom, left = [int(v / SCALE) for v in (top, right, bottom, left)]
        cv2.rectangle(show, (left, top), (right, bottom), (0, 255, 0), 3)

    status = "FACE OK - SPACE dabao" if len(faces) == 1 else f"{len(faces)} face mile"
    color = (0, 255, 0) if len(faces) == 1 else (0, 0, 255)
    cv2.putText(show, f"{count}/{TARGET}  {status}  Q=quit",
                (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
    cv2.imshow("Register Student", show)

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    if key == 32:  # SPACE
        if len(faces) == 1:
            count += 1
            cv2.imwrite(f"{folder}/{count}.jpg", frame)
            print(f"Saved {count}/{TARGET}")
        else:
            print(f"{len(faces)} face mile, sirf 1 hona chahiye")

cam.release()
cv2.destroyAllWindows()
print(f"Done! {count} photos save hui: {folder}")
