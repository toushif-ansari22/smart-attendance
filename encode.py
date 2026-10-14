import cv2
import os
import pickle
import face_recognition

DATASET = "dataset"
OUTPUT = "encodings.pickle"
MAX_WIDTH = 640   # bade face wali problem se bachne ke liye photo chhoti karte hain

known_encodings = []
known_names = []

for person in sorted(os.listdir(DATASET)):
    person_path = os.path.join(DATASET, person)
    if not os.path.isdir(person_path):
        continue

    # folder ka naam: 101_Toushif  ->  roll=101, name=Toushif
    roll, name = person.split("_", 1)
    label = f"{roll}|{name}"

    done = 0
    for img_name in sorted(os.listdir(person_path)):
        if not img_name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        img = cv2.imread(os.path.join(person_path, img_name))
        if img is None:
            print(f"  {img_name}: padh nahi payi, skip")
            continue

        # photo chhoti karo
        h, w = img.shape[:2]
        if w > MAX_WIDTH:
            scale = MAX_WIDTH / w
            img = cv2.resize(img, (0, 0), fx=scale, fy=scale)

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb)

        if len(boxes) != 1:
            print(f"  {img_name}: {len(boxes)} face mile, skip")
            continue

        enc = face_recognition.face_encodings(rgb, boxes)[0]
        known_encodings.append(enc)
        known_names.append(label)
        done += 1

    print(f"{person}: {done} photos encode hui")

with open(OUTPUT, "wb") as f:
    pickle.dump({"encodings": known_encodings, "names": known_names}, f)

print(f"\nDone! Total {len(known_encodings)} encodings save hui: {OUTPUT}")
