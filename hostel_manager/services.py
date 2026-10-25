"""Business logic on top of SQLite. Raises ValidationError with friendly messages."""
import csv
import sqlite3
from datetime import date

from . import db
from .utils import (ValidationError, current_month, month_range, now_str, optional_phone,
                    parse_amount, parse_date, parse_datetime, parse_int, parse_month, required,
                    today_str)

PAYMENT_METHODS = ("Cash", "UPI", "Bank")
MAINT_STATUSES = ("Open", "In Progress", "Completed")
MAINT_CATEGORIES = ("Electrical", "Plumbing", "Cleaning", "Furniture", "Fan/AC", "Other")
EXPENSE_CATEGORIES = ("Electricity", "Water", "Groceries", "Salaries", "Repairs", "Miscellaneous")
ID_PROOFS = ("Aadhaar", "Driving Licence", "Voter ID", "PAN", "Passport", "College/Office ID", "Other")


class Service:
    def __init__(self, conn):
        self.conn = conn

    def _all(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    # ---- auth ----
    def login(self, username, password):
        return db.verify_password(self.conn, (username or "").strip(), password or "")

    def change_password(self, username, old, new, confirm):
        if not db.verify_password(self.conn, username, old or ""):
            raise ValidationError("Current password is incorrect.")
        if len(new or "") < 6:
            raise ValidationError("New password must be at least 6 characters.")
        if new != confirm:
            raise ValidationError("New password and confirmation do not match.")
        db.set_password(self.conn, username, new)

    # ---- rooms ----
    def list_rooms(self):
        return self._all(
            """SELECT r.id, r.room_no, r.capacity,
                      (SELECT COUNT(*) FROM residents x WHERE x.room_id=r.id AND x.status='Active') AS occupied
               FROM rooms r ORDER BY CAST(r.room_no AS INTEGER), r.room_no""")

    def room_occupancy(self):
        rows = self.list_rooms()
        names = {}
        for r in self._all("SELECT room_id, name FROM residents WHERE status='Active' ORDER BY bed_no"):
            names.setdefault(r["room_id"], []).append(r["name"])
        for r in rows:
            r["vacant"] = r["capacity"] - r["occupied"]
            r["residents"] = ", ".join(names.get(r["id"], []))
        return rows

    def save_room(self, room_no, capacity, room_id=None):
        room_no = required(room_no, "Room number")
        capacity = parse_int(capacity, "Bed capacity", minimum=1)
        if room_id:
            occupied_max = self.conn.execute(
                "SELECT COALESCE(MAX(bed_no),0) FROM residents WHERE room_id=? AND status='Active'",
                (room_id,)).fetchone()[0]
            if capacity < occupied_max:
                raise ValidationError(f"Cannot reduce capacity below {occupied_max}: bed {occupied_max} is occupied.")
        try:
            if room_id:
                self.conn.execute("UPDATE rooms SET room_no=?, capacity=? WHERE id=?", (room_no, capacity, room_id))
            else:
                self.conn.execute("INSERT INTO rooms(room_no, capacity) VALUES (?,?)", (room_no, capacity))
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ValidationError(f"Room {room_no} already exists.")

    def delete_room(self, room_id):
        used = self.conn.execute(
            "SELECT (SELECT COUNT(*) FROM residents WHERE room_id=?)+(SELECT COUNT(*) FROM maintenance WHERE room_id=?)"
            "+(SELECT COUNT(*) FROM visitors WHERE room_id=?)", (room_id,) * 3).fetchone()[0]
        if used:
            raise ValidationError("This room has residents/records linked to it and cannot be deleted.")
        self.conn.execute("DELETE FROM rooms WHERE id=?", (room_id,))
        self.conn.commit()

    def free_beds(self, room_id, exclude_resident_id=None):
        room = self.conn.execute("SELECT capacity FROM rooms WHERE id=?", (room_id,)).fetchone()
        if not room:
            return []
        taken = {r[0] for r in self.conn.execute(
            "SELECT bed_no FROM residents WHERE room_id=? AND status='Active' AND id IS NOT ?",
            (room_id, exclude_resident_id))}
        return [b for b in range(1, room["capacity"] + 1) if b not in taken]

    # ---- residents ----
    def list_residents(self, status=None, search=""):
        sql = """SELECT x.*, r.room_no FROM residents x LEFT JOIN rooms r ON r.id=x.room_id WHERE 1=1"""
        params = []
        if status:
            sql += " AND x.status=?"
            params.append(status)
        if search:
            sql += " AND (x.name LIKE ? OR x.phone LIKE ?)"
            params += [f"%{search}%"] * 2
        return self._all(sql + " ORDER BY x.name", params)

    def get_resident(self, resident_id):
        rows = self._all("SELECT x.*, r.room_no FROM residents x LEFT JOIN rooms r ON r.id=x.room_id WHERE x.id=?",
                         (resident_id,))
        return rows[0] if rows else None

    def save_resident(self, data, resident_id=None):
        clean = {
            "name": required(data.get("name"), "Name"),
            "phone": optional_phone(data.get("phone"), "Phone", True),
            "address": required(data.get("address"), "Address"),
            "id_proof_type": required(data.get("id_proof_type"), "ID proof type"),
            "id_proof_number": required(data.get("id_proof_number"), "ID proof number"),
            "emergency_name": required(data.get("emergency_name"), "Emergency contact name"),
            "emergency_phone": optional_phone(data.get("emergency_phone"), "Emergency contact phone", True),
            "join_date": parse_date(data.get("join_date"), "Join date"),
            "monthly_rent": parse_amount(data.get("monthly_rent"), "Monthly rent", allow_zero=False),
            "deposit": parse_amount(data.get("deposit") or "0", "Advance/deposit"),
        }
        room_id = data.get("room_id")
        if not room_id:
            raise ValidationError("Please assign a room.")
        room_id = int(room_id)
        bed_no = parse_int(data.get("bed_no"), "Bed number", minimum=1)
        room = self.conn.execute("SELECT room_no, capacity FROM rooms WHERE id=?", (room_id,)).fetchone()
        if not room:
            raise ValidationError("Selected room does not exist.")
        if bed_no > room["capacity"]:
            raise ValidationError(f"Room {room['room_no']} has only {room['capacity']} bed(s).")
        if resident_id:
            existing = self.get_resident(resident_id)
            if not existing:
                raise ValidationError("Resident not found.")
            if existing["status"] != "Active":
                raise ValidationError("Checked-out residents cannot be edited.")
        if bed_no not in self.free_beds(room_id, resident_id):
            raise ValidationError(f"Bed {bed_no} in room {room['room_no']} is already occupied.")
        clean.update(room_id=room_id, bed_no=bed_no)
        cols = list(clean)
        if resident_id:
            self.conn.execute(f"UPDATE residents SET {', '.join(c + '=?' for c in cols)} WHERE id=?",
                              [clean[c] for c in cols] + [resident_id])
        else:
            self.conn.execute(
                f"INSERT INTO residents({', '.join(cols)}, status) VALUES ({', '.join('?' * len(cols))}, 'Active')",
                [clean[c] for c in cols])
        self.conn.commit()

    def checkout_resident(self, resident_id, checkout_date=None):
        res = self.get_resident(resident_id)
        if not res or res["status"] != "Active":
            raise ValidationError("Only active residents can be checked out.")
        cdate = parse_date(checkout_date or today_str(), "Check-out date")
        if cdate < res["join_date"]:
            raise ValidationError("Check-out date cannot be before the join date.")
        self.conn.execute("UPDATE residents SET status='Checked Out', checkout_date=? WHERE id=?",
                          (cdate, resident_id))
        self.conn.commit()

    # ---- rent ----
    def _next_receipt_no(self):
        row = self.conn.execute("SELECT MAX(id) FROM payments").fetchone()[0] or 0
        n = row + 1
        while True:
            no = f"RCPT-{n:05d}"
            if not self.conn.execute("SELECT 1 FROM payments WHERE receipt_no=?", (no,)).fetchone():
                return no
            n += 1

    def record_payment(self, resident_id, month, amount, payment_date, method, notes=""):
        res = self.get_resident(resident_id) if resident_id else None
        if not res:
            raise ValidationError("Please select a resident.")
        month = parse_month(month, "Rent month")
        amount = parse_amount(amount, "Amount", allow_zero=False)
        payment_date = parse_date(payment_date, "Payment date")
        if method not in PAYMENT_METHODS:
            raise ValidationError("Payment method must be Cash, UPI or Bank.")
        receipt_no = self._next_receipt_no()
        cur = self.conn.execute(
            "INSERT INTO payments(resident_id, month, amount, payment_date, method, receipt_no, notes)"
            " VALUES (?,?,?,?,?,?,?)", (resident_id, month, amount, payment_date, method, receipt_no, notes.strip()))
        self.conn.commit()
        return cur.lastrowid

    def list_payments(self, month=None):
        sql = ("SELECT p.*, x.name AS resident_name, r.room_no FROM payments p "
               "JOIN residents x ON x.id=p.resident_id LEFT JOIN rooms r ON r.id=x.room_id")
        params = []
        if month:
            sql += " WHERE p.month=?"
            params.append(month)
        return self._all(sql + " ORDER BY p.payment_date DESC, p.id DESC", params)

    def get_payment(self, payment_id):
        rows = self._all(
            "SELECT p.*, x.name AS resident_name, x.phone, r.room_no, x.bed_no FROM payments p "
            "JOIN residents x ON x.id=p.resident_id LEFT JOIN rooms r ON r.id=x.room_id WHERE p.id=?",
            (payment_id,))
        return rows[0] if rows else None

    def pending_rent(self, as_of_month=None, include_checked_out=False):
        """Per-resident outstanding rent: (months from join month to now) x rent - total paid."""
        as_of_month = as_of_month or current_month()
        out = []
        for res in self.list_residents(None if include_checked_out else "Active"):
            last = as_of_month
            if res["checkout_date"]:
                last = min(last, res["checkout_date"][:7])
            start = res["join_date"][:7]
            months = len(list(month_range(start, last))) if start <= last else 0
            due = months * res["monthly_rent"]
            paid = self.conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE resident_id=?",
                                     (res["id"],)).fetchone()[0]
            if due - paid > 0.004:
                out.append({"resident_id": res["id"], "name": res["name"], "room_no": res["room_no"],
                            "monthly_rent": res["monthly_rent"], "months_due": months,
                            "total_due": due, "total_paid": paid, "outstanding": round(due - paid, 2)})
        return sorted(out, key=lambda r: -r["outstanding"])

    def month_collection(self, month=None):
        month = month or current_month()
        return self.conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE payment_date LIKE ?",
                                 (month + "%",)).fetchone()[0]

    # ---- maintenance ----
    def list_maintenance(self, status=None):
        sql = "SELECT m.*, r.room_no FROM maintenance m LEFT JOIN rooms r ON r.id=m.room_id"
        params = []
        if status:
            sql += " WHERE m.status=?"
            params.append(status)
        return self._all(sql + " ORDER BY m.reported_date DESC, m.id DESC", params)

    def save_maintenance(self, data, item_id=None):
        clean = {
            "room_id": int(data["room_id"]) if data.get("room_id") else None,
            "category": required(data.get("category"), "Category"),
            "description": required(data.get("description"), "Description"),
            "reported_date": parse_date(data.get("reported_date"), "Reported date"),
            "assigned_to": (data.get("assigned_to") or "").strip(),
            "cost": parse_amount(data.get("cost") or "0", "Cost"),
            "status": data.get("status"),
        }
        if clean["status"] not in MAINT_STATUSES:
            raise ValidationError("Status must be Open, In Progress or Completed.")
        cols = list(clean)
        if item_id:
            self.conn.execute(f"UPDATE maintenance SET {', '.join(c + '=?' for c in cols)} WHERE id=?",
                              [clean[c] for c in cols] + [item_id])
        else:
            self.conn.execute(f"INSERT INTO maintenance({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                              [clean[c] for c in cols])
        self.conn.commit()

    def delete_maintenance(self, item_id):
        self.conn.execute("DELETE FROM maintenance WHERE id=?", (item_id,))
        self.conn.commit()

    # ---- expenses ----
    def list_expenses(self, month=None):
        sql = "SELECT * FROM expenses"
        params = []
        if month:
            sql += " WHERE expense_date LIKE ?"
            params.append(month + "%")
        return self._all(sql + " ORDER BY expense_date DESC, id DESC", params)

    def save_expense(self, data, expense_id=None):
        clean = {
            "expense_date": parse_date(data.get("expense_date"), "Expense date"),
            "category": required(data.get("category"), "Category"),
            "description": (data.get("description") or "").strip(),
            "amount": parse_amount(data.get("amount"), "Amount", allow_zero=False),
        }
        cols = list(clean)
        if expense_id:
            self.conn.execute(f"UPDATE expenses SET {', '.join(c + '=?' for c in cols)} WHERE id=?",
                              [clean[c] for c in cols] + [expense_id])
        else:
            self.conn.execute(f"INSERT INTO expenses({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                              [clean[c] for c in cols])
        self.conn.commit()

    def delete_expense(self, expense_id):
        self.conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
        self.conn.commit()

    # ---- visitors ----
    def list_visitors(self):
        return self._all(
            "SELECT v.*, x.name AS resident_name, r.room_no FROM visitors v "
            "LEFT JOIN residents x ON x.id=v.resident_id LEFT JOIN rooms r ON r.id=v.room_id "
            "ORDER BY v.check_in DESC, v.id DESC")

    def add_visitor(self, data):
        name = required(data.get("name"), "Visitor name")
        phone = optional_phone(data.get("phone"), "Visitor phone")
        check_in = parse_datetime(data.get("check_in") or now_str(), "Check-in")
        check_out = parse_datetime(data.get("check_out"), "Check-out", allow_empty=True)
        if check_out and check_out < check_in:
            raise ValidationError("Check-out cannot be before check-in.")
        resident_id = data.get("resident_id") or None
        room_id = data.get("room_id") or None
        if resident_id:
            res = self.get_resident(int(resident_id))
            room_id = res["room_id"] if res else room_id
        if not resident_id and not room_id:
            raise ValidationError("Select the resident or room being visited.")
        self.conn.execute(
            "INSERT INTO visitors(name, phone, resident_id, room_id, check_in, check_out) VALUES (?,?,?,?,?,?)",
            (name, phone, resident_id, room_id, check_in, check_out))
        self.conn.commit()

    def visitor_checkout(self, visitor_id, check_out=None):
        row = self.conn.execute("SELECT check_in, check_out FROM visitors WHERE id=?", (visitor_id,)).fetchone()
        if not row:
            raise ValidationError("Visitor entry not found.")
        if row["check_out"]:
            raise ValidationError("This visitor is already checked out.")
        co = parse_datetime(check_out or now_str(), "Check-out")
        if co < row["check_in"]:
            raise ValidationError("Check-out cannot be before check-in.")
        self.conn.execute("UPDATE visitors SET check_out=? WHERE id=?", (co, visitor_id))
        self.conn.commit()

    # ---- dashboard / reports ----
    def dashboard(self):
        rooms = self.list_rooms()
        total_beds = sum(r["capacity"] for r in rooms)
        occupied = sum(r["occupied"] for r in rooms)
        return {
            "total_rooms": len(rooms), "total_beds": total_beds, "occupied_beds": occupied,
            "vacant_beds": total_beds - occupied, "month_collection": self.month_collection(),
            "outstanding_rent": round(sum(p["outstanding"] for p in self.pending_rent()), 2),
            "open_maintenance": self.conn.execute(
                "SELECT COUNT(*) FROM maintenance WHERE status != 'Completed'").fetchone()[0],
        }

    def expense_summary(self, month=None):
        sql = "SELECT category, COUNT(*) AS entries, SUM(amount) AS total FROM expenses"
        params = []
        if month:
            sql += " WHERE expense_date LIKE ?"
            params.append(month + "%")
        return self._all(sql + " GROUP BY category ORDER BY total DESC", params)

    def income_vs_expense(self, month):
        income = self.conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE payment_date LIKE ?",
                                   (month + "%",)).fetchone()[0]
        spent = self.conn.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE expense_date LIKE ?",
                                  (month + "%",)).fetchone()[0]
        return {"month": month, "income": income, "expenses": spent, "net": round(income - spent, 2)}


def export_csv(path, rows, columns):
    """Write rows (list of dicts) to CSV; columns is a list of (key, heading)."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([h for _, h in columns])
        for r in rows:
            w.writerow([r.get(k, "") for k, _ in columns])
