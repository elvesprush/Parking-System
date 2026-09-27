# SmartPark KE — Automated Parking Management System

A web-based parking system built with **Python (Flask)** and **SQLite**, developed
for the Multimedia University of Kenya Data Structures & Algorithms client
brief: automate a parking lot so drivers can see slot availability before
entry, have their vehicle timed automatically, and pay a tiered exit fee
before the barrier opens.

## Pages (sidebar navigation)
- **Dashboard** — welcome banner, stat cards (Total / Available / VIP / Occupied), live colour-coded slot grid, and an info panel.
- **Park Vehicle** — entry form (plate number + optional "VIP customer" checkbox) that records arrival and auto-assigns a slot.
- **My Vehicles** — live table of every vehicle currently parked, with a running fee estimate and a quick "Pay & Exit" link.
- **Payment** — look up a plate, see the calculated duration/fee, and confirm payment to "open the barrier".
- **History** — log of every completed (paid) parking session plus total revenue collected.
- **Settings** — read-only summary of the current slot count, VIP slots, and fee tiers.
- **Login/Logout** — simple session-based name so the topbar can say "Welcome, `<name>`" (no password — this is a kiosk-style demo, not a multi-tenant auth system).

## Features / Modules
1. **Slot Display Module** — live grid of free/occupied/VIP bays on the dashboard, labelled A, B, C… like a real parking bay sign.
2. **Vehicle Entry Module** — records plate number + timestamp, auto-assigns a slot (VIP-aware allocation: VIP requests get a VIP bay first, regular requests get a regular bay first, each falling back to the other type only if their preferred type is full).
3. **Fee Calculation Module** — computes minutes parked and applies the tiered fee.
4. **Barrier Control Module** — "opens the barrier" (receipt page) once fee is paid; auto-promotes the next queued car into a freed slot.
5. **Database Module** — dynamic SQLite database (`smartpark.db`), created automatically on first run.

## Fee Structure (as specified by the client)
| Duration            | Fee (Kshs.) |
|----------------------|-------------|
| Up to 30 minutes     | Free        |
| Up to 2 hours        | 50          |
| Up to 4 hours        | 100         |
| Up to 6 hours        | 300         |
| Over 6 hours         | 500         |

## Project Structure
```
smartpark_ke/
├── app.py            # Flask routes + algorithms (entry, fee calc, exit, barrier)
├── database.py       # SQLite dynamic database layer
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── index.html    # dashboard: slot display + entry/exit forms
│   ├── exit.html      # fee summary before payment
│   └── receipt.html   # payment confirmation / barrier open
└── static/
    └── style.css
```

## Setup & Run
```bash
# 1. Clone the repo
git clone <your-repo-url>
cd smartpark_ke

# 2. (Optional but recommended) create a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```
Then open **http://127.0.0.1:5000** in your browser. The SQLite database
(`smartpark.db`) and its tables are created automatically the first time you
run the app — no manual database setup needed.

## How to Use
1. Open the app — you'll land on **Login**. Type any name (no password needed,
   this just personalises the "Welcome, ..." greeting) and click **Enter Parking System**.
2. The **Dashboard** shows live stats (total/available/VIP/occupied slots) and
   a colour-coded slot grid: green = available, red = occupied, gold = VIP
   available, orange = VIP occupied.
3. Click **Park Vehicle** in the sidebar, type a number plate, optionally tick
   "Reserve a VIP slot", and click **Record Arrival** — the system timestamps
   it and auto-assigns a slot (VIP-aware allocation).
4. Click **My Vehicles** to see every car currently parked with a running
   time/fee estimate, or go straight to **Payment**.
5. On **Payment**, type the plate and click **Look Up** to see the calculated
   duration and fee, then **Pay & Open Barrier** to confirm — the slot is
   freed and, if a vehicle was waiting in the queue, it's automatically
   assigned that slot.
6. Check **History** for a full log of completed sessions and total revenue
   collected, or **Settings** for a read-only summary of the current
   configuration (slot count, VIP slots, fee tiers).

## Data Structures Used
- **Hash map (`dict` / SQLite indexed table)** — O(1) lookup of a slot's status by `slot_id`.
- **Queue (`collections.deque`)** — FIFO waiting list for vehicles when the lot is full.
- **List** — ordered slot grid for the visual display.

See the accompanying design report (Task One) for the full algorithm
pseudocode, data-structure justification, and dynamic database design.

## Author
Individual submission — Data Structures & Algorithms, Multimedia University of Kenya.
