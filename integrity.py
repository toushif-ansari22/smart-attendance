"""Tamper-evident attendance log.

Every attendance record stores an HMAC-SHA256 hash that covers the record
data and the hash of the previous record. Editing or deleting any record
breaks the chain, and the break is found by verify().

Commands:
    python integrity.py verify [db]
    python integrity.py rebuild [db]            (admin: re-seal all records)
    python integrity.py delete-today ROLL [db]  (admin: remove today's record, then re-seal)
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
import sys
from datetime import datetime

KEY_FILE = ".att_key"
GENESIS = "GENESIS"


def _key():
    env = os.environ.get("ATT_SECRET")
    if env:
        return env.encode()
    if not os.path.exists(KEY_FILE):
        with open(KEY_FILE, "w") as f:
            f.write(secrets.token_hex(32))
        os.chmod(KEY_FILE, 0o600)
    with open(KEY_FILE) as f:
        return f.read().strip().encode()


def _sign(*parts):
    msg = "|".join(str(p) for p in parts).encode()
    return hmac.new(_key(), msg, hashlib.sha256).hexdigest()


def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def _entry_hash(prev, roll, date, tm, conf, blinks):
    return _sign(prev, roll, date, tm, _fmt(conf), _fmt(blinks))


def _meta_sig(last_id, last_hash):
    return _sign("META", last_id, last_hash)


def ensure_schema(conn):
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        UNIQUE(roll_no, date))""")
    cols = [r[1] for r in cur.execute("PRAGMA table_info(attendance)").fetchall()]
    for name, typ in (("confidence", "REAL"), ("blinks", "INTEGER"),
                      ("prev_hash", "TEXT"), ("entry_hash", "TEXT")):
        if name not in cols:
            cur.execute(f"ALTER TABLE attendance ADD COLUMN {name} {typ}")
    cur.execute("""CREATE TABLE IF NOT EXISTS chain_meta (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        last_id INTEGER,
        last_hash TEXT,
        sig TEXT)""")
    conn.commit()


def _write_meta(cur, last_id, last_hash):
    cur.execute(
        "INSERT OR REPLACE INTO chain_meta (id, last_id, last_hash, sig) VALUES (1, ?, ?, ?)",
        (last_id, last_hash, _meta_sig(last_id, last_hash)))


def add_entry(conn, roll, confidence=None, blinks=None):
    """Add today's attendance for roll. Returns True if added, False if already marked."""
    cur = conn.cursor()
    now = datetime.now()
    date, tm = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

    cur.execute("SELECT 1 FROM attendance WHERE roll_no=? AND date=?", (roll, date))
    if cur.fetchone():
        return False

    cur.execute("SELECT COUNT(*) FROM attendance")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE entry_hash IS NULL")
    if cur.fetchone()[0]:
        raise RuntimeError("Unsealed records found. Run: python integrity.py rebuild")

    cur.execute("SELECT last_id, last_hash FROM chain_meta WHERE id=1")
    m = cur.fetchone()
    if m is None:
        if total:
            raise RuntimeError("Chain head is missing. Run: python integrity.py verify")
        prev = GENESIS
    else:
        prev = m[1]

    if confidence is not None:
        confidence = round(float(confidence), 4)
    h = _entry_hash(prev, roll, date, tm, confidence, blinks)
    cur.execute(
        "INSERT INTO attendance (roll_no, date, time, confidence, blinks, prev_hash, entry_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (roll, date, tm, confidence, blinks, prev, h))
    _write_meta(cur, cur.lastrowid, h)
    conn.commit()
    return True


def _result(status, checked, broken_id, message):
    return {"status": status, "checked": checked,
            "broken_id": broken_id, "message": message}


def verify(conn):
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(attendance)").fetchall()]
    if "entry_hash" not in cols:
        return _result("unsealed", 0, None,
                       "No integrity chain in this database yet. Run: python integrity.py rebuild")

    rows = cur.execute(
        "SELECT id, roll_no, date, time, confidence, blinks, prev_hash, entry_hash "
        "FROM attendance ORDER BY id").fetchall()
    if any(r[7] is None for r in rows):
        return _result("unsealed", len(rows), None,
                       "Some records have no hash yet. Run: python integrity.py rebuild")

    prev = GENESIS
    for i, (id_, roll, date, tm, conf, bl, ph, eh) in enumerate(rows):
        if ph != prev:
            return _result("broken", i, id_,
                           f"Record id {id_}: link to the previous record is broken "
                           f"(a record before it was deleted or changed).")
        if _entry_hash(prev, roll, date, tm, conf, bl) != eh:
            return _result("broken", i, id_, f"Record id {id_} was modified.")
        prev = eh

    try:
        m = cur.execute("SELECT last_id, last_hash, sig FROM chain_meta WHERE id=1").fetchone()
    except sqlite3.OperationalError:
        m = None

    if not rows and m is None:
        return _result("empty", 0, None, "No attendance records yet.")

    last_id = rows[-1][0] if rows else 0
    if m is None or m[0] != last_id or m[1] != prev or m[2] != _meta_sig(m[0], m[1]):
        return _result("broken", len(rows), None,
                       "The newest record was deleted or the chain head was changed.")

    return _result("ok", len(rows), None, f"All {len(rows)} records are intact.")


def rebuild(conn):
    """Admin action: recompute every hash from the current data and re-seal the chain."""
    ensure_schema(conn)
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT id, roll_no, date, time, confidence, blinks "
        "FROM attendance ORDER BY id").fetchall()
    prev = GENESIS
    for id_, roll, date, tm, conf, bl in rows:
        h = _entry_hash(prev, roll, date, tm, conf, bl)
        cur.execute("UPDATE attendance SET prev_hash=?, entry_hash=? WHERE id=?", (prev, h, id_))
        prev = h
    _write_meta(cur, rows[-1][0] if rows else 0, prev)
    conn.commit()
    return len(rows)


def _open(path):
    if not os.path.exists(path):
        print(f"{path} not found.")
        sys.exit(1)
    return sqlite3.connect(path)


def _usage():
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]
    default_db = os.environ.get("ATT_DB", "attendance.db")
    if not args or args[0] not in ("verify", "rebuild", "delete-today"):
        _usage()

    cmd = args[0]
    if cmd == "delete-today":
        if len(args) < 2:
            _usage()
        roll = args[1]
        db = args[2] if len(args) > 2 else default_db
        conn = _open(db)
        ensure_schema(conn)
        today = datetime.now().strftime("%Y-%m-%d")
        cur = conn.cursor()
        cur.execute("DELETE FROM attendance WHERE roll_no=? AND date=?", (roll, today))
        removed = cur.rowcount
        conn.commit()
        n = rebuild(conn)
        print(f"Removed {removed} record(s) for {roll} on {today}. Chain re-sealed ({n} records).")
        conn.close()
    elif cmd == "rebuild":
        db = args[1] if len(args) > 1 else default_db
        conn = _open(db)
        n = rebuild(conn)
        print(f"Chain re-sealed: {n} records.")
        conn.close()
    else:
        db = args[1] if len(args) > 1 else default_db
        conn = _open(db)
        res = verify(conn)
        conn.close()
        print(f"Status : {res['status'].upper()}")
        print(f"Checked: {res['checked']} records")
        print(res["message"])
        sys.exit(0 if res["status"] in ("ok", "empty") else 1)
