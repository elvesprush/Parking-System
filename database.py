"""
database.py
============
MODULE 5: DATABASE MODULE (Dynamic Database Design)

Why SQLite?
-----------
SQLite is a lightweight, file-based, *dynamic* relational database - tables
are created programmatically at start-up (init_db) and every row is
inserted/updated/deleted at runtime as vehicles arrive and leave. No manual
schema editing is ever required.

Schema (2 tables):

    slots
    -----
    slot_id    INTEGER PRIMARY KEY   -- 1 .. TOTAL_SLOTS
    status     TEXT                  -- 'free' | 'occupied'
    slot_type  TEXT                  -- 'regular' | 'vip'

    vehicles
    --------
    id            INTEGER PRIMARY KEY AUTOINCREMENT
    plate         TEXT                  -- number plate, e.g. KDA 123A
    slot_id       INTEGER  (FK -> slots.slot_id)
    entry_time    TEXT (ISO datetime)
    exit_time     TEXT (ISO datetime, NULL while still parked)
    duration_min  INTEGER (NULL while still parked)
    fee           INTEGER (NULL while still parked)
    status        TEXT                  -- 'active' | 'closed'

A vehicle's *current* session is the row with status='active'; exiting
simply UPDATEs that same row rather than deleting it, so the table doubles
as a full historical log/audit-trail of every visit.
"""

import sqlite3
from contextlib import closing

DB_PATH = "smartpark.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts: row["col"]
    return conn


def init_db(total_slots: int, vip_slot_ids=None):
    """
    Creates the tables (if they don't already exist) and seeds the `slots`
    table with `total_slots` free bays, marking the slot_ids listed in
    `vip_slot_ids` as 'vip' and the rest as 'regular'. Safe to call every
    time the app starts - it will not wipe existing data.
    """
    vip_slot_ids = set(vip_slot_ids or [])

    with closing(get_connection()) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS slots (
                slot_id   INTEGER PRIMARY KEY,
                status    TEXT NOT NULL DEFAULT 'free',
                slot_type TEXT NOT NULL DEFAULT 'regular'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                plate        TEXT NOT NULL,
                slot_id      INTEGER NOT NULL,
                entry_time   TEXT NOT NULL,
                exit_time    TEXT,
                duration_min INTEGER,
                fee          INTEGER,
                status       TEXT NOT NULL DEFAULT 'active',
                FOREIGN KEY (slot_id) REFERENCES slots (slot_id)
            )
        """)

        existing = conn.execute("SELECT COUNT(*) AS c FROM slots").fetchone()["c"]
        if existing == 0:
            conn.executemany(
                "INSERT INTO slots (slot_id, status, slot_type) VALUES (?, 'free', ?)",
                [(i, "vip" if i in vip_slot_ids else "regular")
                 for i in range(1, total_slots + 1)],
            )


# ---------------------------------------------------------------------------
# SLOT OPERATIONS
# ---------------------------------------------------------------------------
def get_all_slots():
    with closing(get_connection()) as conn:
        return conn.execute(
            "SELECT slot_id, status, slot_type FROM slots ORDER BY slot_id"
        ).fetchall()


def get_slot_counts():
    """Returns a dict with total/free/occupied/vip counts for the stat cards."""
    slots = get_all_slots()
    total = len(slots)
    free = sum(1 for s in slots if s["status"] == "free")
    vip_total = sum(1 for s in slots if s["slot_type"] == "vip")
    return {
        "total": total,
        "free": free,
        "occupied": total - free,
        "vip_total": vip_total,
    }


def set_slot_status(slot_id: int, status: str):
    with closing(get_connection()) as conn, conn:
        conn.execute(
            "UPDATE slots SET status = ? WHERE slot_id = ?", (status, slot_id)
        )


# ---------------------------------------------------------------------------
# VEHICLE / SESSION OPERATIONS
# ---------------------------------------------------------------------------
def vehicle_is_active(plate: str) -> bool:
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT id FROM vehicles WHERE plate = ? AND status = 'active'",
            (plate,),
        ).fetchone()
        return row is not None


def create_vehicle_record(plate: str, slot_id: int, entry_time):
    with closing(get_connection()) as conn, conn:
        conn.execute(
            """INSERT INTO vehicles (plate, slot_id, entry_time, status)
               VALUES (?, ?, ?, 'active')""",
            (plate, slot_id, entry_time.isoformat()),
        )


def get_active_record(plate: str):
    with closing(get_connection()) as conn:
        return conn.execute(
            "SELECT * FROM vehicles WHERE plate = ? AND status = 'active'",
            (plate,),
        ).fetchone()


def get_active_vehicles():
    with closing(get_connection()) as conn:
        return conn.execute(
            """SELECT v.*, s.slot_type FROM vehicles v
               JOIN slots s ON s.slot_id = v.slot_id
               WHERE v.status = 'active' ORDER BY v.entry_time"""
        ).fetchall()


def close_vehicle_record(record_id: int, exit_time, duration_min: int, fee: int):
    with closing(get_connection()) as conn, conn:
        conn.execute(
            """UPDATE vehicles
               SET exit_time = ?, duration_min = ?, fee = ?, status = 'closed'
               WHERE id = ?""",
            (exit_time.isoformat(), duration_min, fee, record_id),
        )


def get_history(limit: int = 100):
    """Returns the most recent closed sessions - full payment/audit log."""
    with closing(get_connection()) as conn:
        return conn.execute(
            """SELECT * FROM vehicles WHERE status = 'closed'
               ORDER BY exit_time DESC LIMIT ?""",
            (limit,),
        ).fetchall()
