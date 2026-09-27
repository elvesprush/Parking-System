"""
SmartPark KE - Modern Automated Parking Management System
============================================================
Multimedia University of Kenya - Data Structures & Algorithms Task

Five modules identified from the client's terms of reference:

    1. Slot Display Module   -> live grid of parking-slot availability
    2. Vehicle Entry Module  -> records a vehicle on arrival, assigns a slot
    3. Fee Calculation Module-> computes duration + amount owed on exit
    4. Barrier Control Module-> "opens" the barrier once payment is confirmed
    5. Database Module       -> SQLite dynamic database (see database.py)

Data structures used (see design report for full justification):
    - dict / indexed table (hash map): O(1) lookup of a slot by its slot_id
    - collections.deque              : FIFO queue for vehicles when lot full
    - list                           : ordered slot grid for the display
    - ordered list of tuples         : fee brackets (tiered lookup)

Pages (sidebar navigation):
    Dashboard | Park Vehicle | My Vehicles | Payment | History | Settings

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from collections import deque

import database as db

app = Flask(__name__)
app.secret_key = "smartpark-ke-secret-key"  # needed for session + flash messages

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
TOTAL_SLOTS = 20          # size of the parking lot (change freely)
VIP_SLOT_IDS = {1, 2, 3, 4}  # first 4 bays are reserved "VIP / premium" slots
FREE_MINUTES = 30         # first 30 minutes are free

# Fee tiers exactly as specified by the client, checked top-down.
FEE_TIERS = [
    (30,   0),     # up to 30 minutes: free
    (120,  50),    # up to 2 hours:    Kshs. 50
    (240,  100),   # up to 4 hours:    Kshs. 100
    (360,  300),   # up to 6 hours:    Kshs. 300
    (float("inf"), 500),  # over 6 hours: Kshs. 500
]

# ---------------------------------------------------------------------------
# IN-MEMORY WAITING QUEUE (Data Structure: Queue)
# ---------------------------------------------------------------------------
# If every eligible slot is occupied, incoming vehicles are placed in a FIFO
# queue. A deque gives O(1) append/pop from both ends.
waiting_queue = deque()


def slot_label(slot_id: int) -> str:
    """Converts a numeric slot_id into a display letter: 1->A, 2->B, ..."""
    if slot_id <= 26:
        return chr(ord("A") + slot_id - 1)
    return f"S{slot_id}"


app.jinja_env.filters["slot_label"] = slot_label


def format_datetime(value):
    """Jinja filter: turns an ISO datetime string/object into a friendly
    display format, e.g. '26 Sep 2026, 19:02'."""
    if value is None:
        return "-"
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return dt.strftime("%d %b %Y, %H:%M")


app.jinja_env.filters["fmt_dt"] = format_datetime


# ---------------------------------------------------------------------------
# MODULE 3: FEE CALCULATION MODULE
# ---------------------------------------------------------------------------
def calculate_duration_minutes(entry_time: datetime, exit_time: datetime) -> int:
    """
    Algorithm: Duration Calculation
    1. delta = exit_time - entry_time
    2. minutes = delta in seconds / 60, rounded UP (any started minute bills)
    3. return minutes
    """
    delta_seconds = (exit_time - entry_time).total_seconds()
    minutes = int(delta_seconds // 60) + (1 if delta_seconds % 60 > 0 else 0)
    return max(minutes, 0)


def calculate_fee(minutes: int) -> int:
    """
    Algorithm: Tiered Fee Calculation
    Linear scan over a small, fixed, ORDERED lookup table of (max_minutes,
    fee) tuples - a list of tuples is used (not a dict) because the key is
    a *range*, not a discrete value, exactly like a tax bracket table.
    """
    for max_minutes, fee in FEE_TIERS:
        if minutes <= max_minutes:
            return fee
    return FEE_TIERS[-1][1]


# ---------------------------------------------------------------------------
# MODULE 2: VEHICLE ENTRY MODULE  (+ MODULE 1 support: slot allocation)
# ---------------------------------------------------------------------------
def allocate_slot(prefer_vip: bool = False):
    """
    Algorithm: Slot Allocation (Greedy / First-Available, type-aware)
    1. Build the list of free slots (hash-map style O(1) status lookups).
    2. IF prefer_vip: try free VIP slots first, THEN fall back to any free
       regular slot if no VIP slot is free.
       ELSE: try free regular slots first, THEN fall back to a free VIP
       slot only if no regular slot remains (keeps VIP bays reserved for
       premium customers whenever possible).
    3. Return the first matching slot_id, or None if the lot is entirely full.
    """
    slots = db.get_all_slots()
    free_vip = [s["slot_id"] for s in slots if s["status"] == "free" and s["slot_type"] == "vip"]
    free_regular = [s["slot_id"] for s in slots if s["status"] == "free" and s["slot_type"] == "regular"]

    if prefer_vip:
        ordered = free_vip + free_regular
    else:
        ordered = free_regular + free_vip

    return ordered[0] if ordered else None


def _park_vehicle(plate: str, prefer_vip: bool = False):
    """Shared logic used by both the dashboard quick-form and the Park page."""
    plate = plate.strip().upper()
    if not plate:
        return "Please enter a valid number plate.", "error"

    if db.vehicle_is_active(plate):
        return f"Vehicle {plate} is already parked inside.", "error"

    slot_id = allocate_slot(prefer_vip)
    if slot_id is None:
        waiting_queue.append(plate)
        return (f"Parking is FULL. {plate} has been added to the waiting "
                f"queue (position {len(waiting_queue)}).", "warning")

    entry_time = datetime.now()
    db.create_vehicle_record(plate, slot_id, entry_time)
    db.set_slot_status(slot_id, "occupied")
    return f"Vehicle {plate} recorded. Assigned to slot {slot_label(slot_id)}.", "success"


# ---------------------------------------------------------------------------
# AUTH (simple session-based driver name - no password, matches a demo/kiosk
# style system where the "login" just personalises the greeting)
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name", "").strip() or "Driver"
        session["driver_name"] = name
        flash(f"Welcome, {name}!", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("driver_name", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.context_processor
def inject_driver_name():
    return {
        "driver_name": session.get("driver_name", "Driver"),
        "is_logged_in": "driver_name" in session,
    }


# ---------------------------------------------------------------------------
# MODULE 1: SLOT DISPLAY MODULE (Dashboard)
# ---------------------------------------------------------------------------
@app.route("/")
def dashboard():
    slots = db.get_all_slots()
    counts = db.get_slot_counts()
    return render_template(
        "dashboard.html",
        slots=slots,
        counts=counts,
        queue_length=len(waiting_queue),
        active_page="dashboard",
    )


# ---------------------------------------------------------------------------
# MODULE 2: PARK VEHICLE PAGE
# ---------------------------------------------------------------------------
@app.route("/park", methods=["GET", "POST"])
def park_vehicle():
    if request.method == "POST":
        plate = request.form.get("plate", "")
        prefer_vip = request.form.get("vip") == "on"
        message, category = _park_vehicle(plate, prefer_vip)
        flash(message, category)
        return redirect(url_for("dashboard"))

    slots = db.get_all_slots()
    counts = db.get_slot_counts()
    return render_template(
        "park.html", slots=slots, counts=counts, active_page="park"
    )


# ---------------------------------------------------------------------------
# MY VEHICLES PAGE
# ---------------------------------------------------------------------------
@app.route("/vehicles")
def my_vehicles():
    active = db.get_active_vehicles()
    now = datetime.now()
    rows = []
    for v in active:
        entry_time = datetime.fromisoformat(v["entry_time"])
        minutes = calculate_duration_minutes(entry_time, now)
        rows.append({
            "plate": v["plate"],
            "slot_id": v["slot_id"],
            "slot_type": v["slot_type"],
            "entry_time": v["entry_time"],
            "minutes": minutes,
            "running_fee": calculate_fee(minutes),
        })
    return render_template("vehicles.html", rows=rows, active_page="vehicles")


# ---------------------------------------------------------------------------
# MODULE 3 & 4: PAYMENT / EXIT / BARRIER CONTROL
# ---------------------------------------------------------------------------
@app.route("/payment", methods=["GET"])
def payment_lookup():
    plate = request.args.get("plate", "").strip().upper()
    record = None
    minutes = fee = None
    if plate:
        record = db.get_active_record(plate)
        if record is None:
            flash(f"No active parking record found for {plate}.", "error")
        else:
            now = datetime.now()
            entry_time = datetime.fromisoformat(record["entry_time"])
            minutes = calculate_duration_minutes(entry_time, now)
            fee = calculate_fee(minutes)
    return render_template(
        "payment.html", record=record, minutes=minutes, fee=fee,
        plate=plate, active_page="payment",
    )


@app.route("/payment/<plate>/pay", methods=["POST"])
def payment_pay(plate):
    """
    MODULE 4: BARRIER CONTROL MODULE
    Confirms payment, frees the slot, promotes the next queued vehicle
    (if any), and "opens the barrier" (shown on the receipt page).
    """
    record = db.get_active_record(plate)
    if record is None:
        flash(f"No active parking record found for {plate}.", "error")
        return redirect(url_for("payment_lookup"))

    exit_time = datetime.now()
    entry_time = datetime.fromisoformat(record["entry_time"])
    minutes = calculate_duration_minutes(entry_time, exit_time)
    fee = calculate_fee(minutes)

    db.close_vehicle_record(record["id"], exit_time, minutes, fee)
    db.set_slot_status(record["slot_id"], "free")

    promoted = None
    if waiting_queue:
        promoted = waiting_queue.popleft()
        db.create_vehicle_record(promoted, record["slot_id"], datetime.now())
        db.set_slot_status(record["slot_id"], "occupied")

    return render_template(
        "receipt.html",
        plate=plate, minutes=minutes, fee=fee,
        entry_time=entry_time, exit_time=exit_time,
        promoted=promoted, active_page="payment",
    )


# ---------------------------------------------------------------------------
# HISTORY PAGE
# ---------------------------------------------------------------------------
@app.route("/history")
def history():
    records = db.get_history()
    total_revenue = sum(r["fee"] or 0 for r in records)
    return render_template(
        "history.html", records=records, total_revenue=total_revenue,
        active_page="history",
    )


# ---------------------------------------------------------------------------
# SETTINGS PAGE (read-only overview of current configuration)
# ---------------------------------------------------------------------------
@app.route("/settings")
def settings():
    return render_template(
        "settings.html",
        total_slots=TOTAL_SLOTS,
        vip_count=len(VIP_SLOT_IDS),
        vip_labels=[slot_label(i) for i in sorted(VIP_SLOT_IDS)],
        free_minutes=FREE_MINUTES,
        fee_tiers=FEE_TIERS,
        active_page="settings",
    )


if __name__ == "__main__":
    db.init_db(TOTAL_SLOTS, VIP_SLOT_IDS)  # dynamically creates tables + seeds slots
    app.run(debug=True)
