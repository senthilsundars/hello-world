"""Tkinter/ttk user interface."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import db, receipts, services
from .services import Service, export_csv
from .utils import ValidationError, current_month, now_str, today_str


def guard(func):
    """Show validation problems as friendly dialogs instead of tracebacks."""
    def wrapper(*a, **kw):
        try:
            return func(*a, **kw)
        except ValidationError as exc:
            messagebox.showerror("Please check your input", str(exc))
        except Exception as exc:  # noqa: BLE001 - last-resort friendly message
            messagebox.showerror("Unexpected error", f"Something went wrong:\n{exc}")
    return wrapper


class Table(ttk.Frame):
    """Treeview with scrollbar and optional CSV export."""

    def __init__(self, parent, columns, export_name=None, height=14):
        super().__init__(parent)
        self.columns = columns
        self.rows = []
        self.tree = ttk.Treeview(self, columns=[k for k, _, _ in columns], show="headings",
                                 height=height, selectmode="browse")
        for key, heading, width in columns:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor="w")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.export_name = export_name

    def load(self, rows):
        self.rows = rows
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            self.tree.insert("", "end", iid=str(i), values=[self._fmt(r.get(k)) for k, _, _ in self.columns])

    @staticmethod
    def _fmt(v):
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:,.2f}"
        return v

    def selected(self):
        sel = self.tree.selection()
        return self.rows[int(sel[0])] if sel else None

    @guard
    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile=f"{self.export_name or 'report'}.csv")
        if path:
            export_csv(path, self.rows, [(k, h) for k, h, _ in self.columns])
            messagebox.showinfo("Export complete", f"Saved to:\n{path}")


def form(parent, fields, start_row=0):
    """fields: list of (key, label, kind[, values]). Returns dict of tk variables."""
    vars_ = {}
    for i, f in enumerate(fields):
        key, label, kind = f[:3]
        ttk.Label(parent, text=label).grid(row=start_row + i, column=0, sticky="e", padx=4, pady=2)
        var = tk.StringVar()
        if kind == "combo":
            w = ttk.Combobox(parent, textvariable=var, values=f[3], state="readonly", width=28)
        else:
            w = ttk.Entry(parent, textvariable=var, width=31, show="*" if kind == "password" else "")
        w.grid(row=start_row + i, column=1, sticky="w", padx=4, pady=2)
        vars_[key] = var
    return vars_


class Tab(ttk.Frame):
    def __init__(self, parent, svc, app):
        super().__init__(parent, padding=8)
        self.svc, self.app = svc, app

    def refresh(self):
        pass

    def room_choices(self):
        rooms = self.svc.list_rooms()
        self.room_map = {r["room_no"]: r["id"] for r in rooms}
        return list(self.room_map)

    def buttons(self, parent, items):
        for text, cmd in items:
            ttk.Button(parent, text=text, command=cmd).pack(side="left", padx=3, pady=4)


class DashboardTab(Tab):
    LABELS = [("total_rooms", "Total rooms"), ("total_beds", "Total beds"), ("occupied_beds", "Occupied beds"),
              ("vacant_beds", "Vacant beds"), ("month_collection", "Rent collected this month"),
              ("outstanding_rent", "Outstanding rent"), ("open_maintenance", "Open maintenance items")]

    def __init__(self, *a):
        super().__init__(*a)
        self.vars = {}
        for i, (k, label) in enumerate(self.LABELS):
            box = ttk.LabelFrame(self, text=label, padding=14)
            box.grid(row=i // 3, column=i % 3, padx=8, pady=8, sticky="nsew")
            self.vars[k] = tk.StringVar()
            ttk.Label(box, textvariable=self.vars[k], font=("Segoe UI", 20, "bold")).pack()

    def refresh(self):
        d = self.svc.dashboard()
        for k, v in d.items():
            self.vars[k].set(f"{v:,.2f}" if isinstance(v, float) else str(v))


class RoomsTab(Tab):
    def __init__(self, *a):
        super().__init__(*a)
        self.table = Table(self, [("room_no", "Room", 70), ("capacity", "Beds", 60), ("occupied", "Occupied", 80),
                                  ("vacant", "Vacant", 70), ("residents", "Residents", 420)], "rooms")
        self.table.pack(fill="both", expand=True)
        self.table.tree.bind("<<TreeviewSelect>>", self.on_select)
        box = ttk.LabelFrame(self, text="Add / edit room", padding=6)
        box.pack(fill="x")
        self.v = form(box, [("room_no", "Room number", "entry"), ("capacity", "Bed capacity", "entry")])
        bar = ttk.Frame(box)
        bar.grid(row=2, column=0, columnspan=2)
        self.buttons(bar, [("Add room", self.add), ("Update selected", self.update),
                           ("Delete selected", self.delete), ("Export CSV", self.table.export)])

    def on_select(self, _):
        r = self.table.selected()
        if r:
            self.v["room_no"].set(r["room_no"])
            self.v["capacity"].set(r["capacity"])

    @guard
    def add(self):
        self.svc.save_room(self.v["room_no"].get(), self.v["capacity"].get())
        self.app.refresh_all()

    @guard
    def update(self):
        r = self.table.selected()
        if not r:
            raise ValidationError("Select a room first.")
        self.svc.save_room(self.v["room_no"].get(), self.v["capacity"].get(), r["id"])
        self.app.refresh_all()

    @guard
    def delete(self):
        r = self.table.selected()
        if not r:
            raise ValidationError("Select a room first.")
        if messagebox.askyesno("Delete room", f"Delete room {r['room_no']}?"):
            self.svc.delete_room(r["id"])
            self.app.refresh_all()

    def refresh(self):
        self.table.load(self.svc.room_occupancy())


class ResidentsTab(Tab):
    FIELDS = [("name", "Name", "entry"), ("phone", "Phone", "entry"), ("address", "Address", "entry"),
              ("id_proof_type", "ID proof type", "combo", services.ID_PROOFS),
              ("id_proof_number", "ID proof number", "entry"), ("emergency_name", "Emergency contact", "entry"),
              ("emergency_phone", "Emergency phone", "entry"), ("join_date", "Join date (YYYY-MM-DD)", "entry"),
              ("monthly_rent", "Monthly rent", "entry"), ("deposit", "Advance / deposit", "entry"),
              ("company_name", "Working / company name (optional)", "entry"),
              ("company_address", "Company address (optional)", "entry")]

    def __init__(self, *a):
        super().__init__(*a)
        self.editing = None
        top = ttk.Frame(self)
        top.pack(fill="x")
        self.show = tk.StringVar(value="Active")
        ttk.Label(top, text="Show:").pack(side="left")
        cb = ttk.Combobox(top, textvariable=self.show, values=("Active", "Checked Out", "All"), width=12,
                          state="readonly")
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        self.table = Table(self, [("name", "Name", 140), ("phone", "Phone", 100),
                                  ("company_name", "Company", 130), ("room_no", "Room", 60),
                                  ("bed_no", "Bed", 40), ("join_date", "Joined", 90),
                                  ("monthly_rent", "Rent", 80), ("deposit", "Deposit", 80),
                                  ("status", "Status", 90), ("checkout_date", "Checked out", 90)],
                           "residents", height=8)
        self.table.pack(fill="both", expand=True)
        self.table.tree.bind("<<TreeviewSelect>>", self.on_select)
        box = ttk.LabelFrame(self, text="Resident details", padding=6)
        box.pack(fill="x")
        self.v = form(box, self.FIELDS)
        self.v["join_date"].set(today_str())
        self.room = tk.StringVar()
        self.bed = tk.StringVar()
        ttk.Label(box, text="Room").grid(row=0, column=2, sticky="e")
        self.room_cb = ttk.Combobox(box, textvariable=self.room, state="readonly", width=10)
        self.room_cb.grid(row=0, column=3, sticky="w")
        self.room_cb.bind("<<ComboboxSelected>>", lambda _: self.update_beds())
        ttk.Label(box, text="Free bed").grid(row=1, column=2, sticky="e")
        self.bed_cb = ttk.Combobox(box, textvariable=self.bed, state="readonly", width=10)
        self.bed_cb.grid(row=1, column=3, sticky="w")
        self.photo_source = ""
        self.stored_photo = ""
        self.photo_status = tk.StringVar(value="No photo")
        photo = ttk.Frame(box)
        photo.grid(row=2, column=2, columnspan=2, rowspan=4, sticky="nw", padx=4)
        ttk.Button(photo, text="Choose photo…", command=self.choose_photo).pack(anchor="w")
        ttk.Button(photo, text="Remove photo", command=self.remove_photo).pack(anchor="w", pady=2)
        ttk.Label(photo, textvariable=self.photo_status, wraplength=180).pack(anchor="w")
        bar = ttk.Frame(box)
        bar.grid(row=len(self.FIELDS), column=0, columnspan=4)
        self.buttons(bar, [("Save new", self.save_new), ("Update selected", self.update),
                           ("Check out selected", self.checkout), ("Clear form", self.clear),
                           ("Export CSV", self.table.export)])

    def update_beds(self):
        rid = self.room_map.get(self.room.get())
        beds = self.svc.free_beds(rid, self.editing) if rid else []
        self.bed_cb["values"] = beds
        if self.bed.get() and int(self.bed.get() or 0) not in beds:
            self.bed.set("")

    def show_photo_status(self):
        if self.photo_source:
            self.photo_status.set(f"Selected: {os.path.basename(self.photo_source)} (saved on Save/Update)")
        elif self.stored_photo:
            self.photo_status.set(f"Stored: {os.path.basename(self.stored_photo)}")
        else:
            self.photo_status.set("No photo")

    def choose_photo(self):
        exts = " ".join("*" + e for e in services.PHOTO_EXTENSIONS)
        path = filedialog.askopenfilename(title="Choose resident photo",
                                          filetypes=[("Image files", exts), ("All files", "*.*")])
        if path:
            self.photo_source = path
            self.show_photo_status()

    @guard
    def remove_photo(self):
        if self.photo_source:
            self.photo_source = ""
        elif self.stored_photo and self.editing:
            if not messagebox.askyesno("Remove photo", "Permanently delete this resident's stored photo?"):
                return
            self.svc.clear_resident_photo(self.editing)
            self.stored_photo = ""
            self.app.refresh_all()
        self.show_photo_status()

    def collect(self):
        d = {k: v.get() for k, v in self.v.items()}
        d["photo_source"] = self.photo_source
        d["room_id"] = self.room_map.get(self.room.get())
        d["bed_no"] = self.bed.get()
        return d

    def on_select(self, _):
        r = self.table.selected()
        if not r:
            return
        self.editing = r["id"] if r["status"] == "Active" else None
        for k, var in self.v.items():
            var.set("" if r.get(k) is None else r[k])
        self.room.set(r["room_no"] or "")
        self.update_beds()
        self.bed.set(r["bed_no"] or "")
        self.photo_source = ""
        self.stored_photo = r.get("photo_path") or ""
        self.show_photo_status()

    def clear(self):
        self.editing = None
        for var in self.v.values():
            var.set("")
        self.v["join_date"].set(today_str())
        self.room.set("")
        self.bed.set("")
        self.photo_source = ""
        self.stored_photo = ""
        self.show_photo_status()
        self.update_beds()

    @guard
    def save_new(self):
        self.svc.save_resident(self.collect())
        self.clear()
        self.app.refresh_all()

    @guard
    def update(self):
        if not self.editing:
            raise ValidationError("Select an active resident in the list to update.")
        self.svc.save_resident(self.collect(), self.editing)
        self.photo_source = ""
        self.stored_photo = (self.svc.get_resident(self.editing) or {}).get("photo_path") or ""
        self.show_photo_status()
        self.app.refresh_all()

    @guard
    def checkout(self):
        r = self.table.selected()
        if not r:
            raise ValidationError("Select a resident first.")
        if messagebox.askyesno("Check out", f"Check out {r['name']} today? The bed will become vacant."):
            self.svc.checkout_resident(r["id"])
            self.clear()
            self.app.refresh_all()

    def refresh(self):
        self.room_cb["values"] = self.room_choices()
        status = None if self.show.get() == "All" else self.show.get()
        self.table.load(self.svc.list_residents(status))


class RentTab(Tab):
    def __init__(self, *a):
        super().__init__(*a)
        self.table = Table(self, [("receipt_no", "Receipt", 90), ("resident_name", "Resident", 140),
                                  ("room_no", "Room", 60), ("month", "Month", 70), ("amount", "Amount", 90),
                                  ("payment_date", "Paid on", 90), ("method", "Method", 70)],
                           "payments", height=8)
        self.table.pack(fill="both", expand=True)
        box = ttk.LabelFrame(self, text="Record payment", padding=6)
        box.pack(fill="x")
        self.resident = tk.StringVar()
        ttk.Label(box, text="Resident").grid(row=0, column=0, sticky="e", padx=4)
        self.res_cb = ttk.Combobox(box, textvariable=self.resident, state="readonly", width=34)
        self.res_cb.grid(row=0, column=1, sticky="w")
        self.v = form(box, [("month", "Rent month (YYYY-MM)", "entry"), ("amount", "Amount", "entry"),
                            ("payment_date", "Payment date", "entry"),
                            ("method", "Method", "combo", services.PAYMENT_METHODS),
                            ("notes", "Notes", "entry")], 1)
        self.v["month"].set(current_month())
        self.v["payment_date"].set(today_str())
        self.v["method"].set("Cash")
        bar = ttk.Frame(box)
        bar.grid(row=6, column=0, columnspan=2)
        self.buttons(bar, [("Save payment && print receipt", self.save), ("Print selected receipt", self.reprint),
                           ("Export CSV", self.table.export)])
        ttk.Label(self, text="Outstanding rent (all months since joining):").pack(anchor="w")
        self.pending = Table(self, [("name", "Resident", 140), ("room_no", "Room", 60),
                                    ("monthly_rent", "Rent", 80), ("months_due", "Months", 60),
                                    ("total_due", "Total due", 90), ("total_paid", "Paid", 90),
                                    ("outstanding", "Outstanding", 90)], "pending_rent", height=5)
        self.pending.pack(fill="both", expand=True)
        ttk.Button(self, text="Export pending CSV", command=self.pending.export).pack(anchor="w")

    @guard
    def save(self):
        res_id = self.res_map.get(self.resident.get())
        pid = self.svc.record_payment(res_id, self.v["month"].get(), self.v["amount"].get(),
                                      self.v["payment_date"].get(), self.v["method"].get(), self.v["notes"].get())
        self.v["amount"].set("")
        self.v["notes"].set("")
        self.app.refresh_all()
        self.open_receipt(pid)

    @guard
    def reprint(self):
        r = self.table.selected()
        if not r:
            raise ValidationError("Select a payment first.")
        self.open_receipt(r["id"])

    def open_receipt(self, pid):
        path = receipts.save_receipt(self.svc.get_payment(pid))
        receipts.open_receipt(path)
        messagebox.showinfo("Receipt", f"Receipt saved to:\n{path}\n\nIt opens in your browser; use Ctrl+P to print.")

    def refresh(self):
        active = self.svc.list_residents("Active")
        self.res_map = {f"{r['name']} (Room {r['room_no']})": r["id"] for r in active}
        self.res_cb["values"] = list(self.res_map)
        self.table.load(self.svc.list_payments())
        self.pending.load(self.svc.pending_rent())


class MaintenanceTab(Tab):
    def __init__(self, *a):
        super().__init__(*a)
        self.table = Table(self, [("room_no", "Room", 60), ("category", "Category", 90),
                                  ("description", "Description", 220), ("reported_date", "Reported", 90),
                                  ("assigned_to", "Assigned to", 110), ("cost", "Cost", 80),
                                  ("status", "Status", 90)], "maintenance", height=10)
        self.table.pack(fill="both", expand=True)
        self.table.tree.bind("<<TreeviewSelect>>", self.on_select)
        box = ttk.LabelFrame(self, text="Maintenance record", padding=6)
        box.pack(fill="x")
        self.room = tk.StringVar()
        ttk.Label(box, text="Room").grid(row=0, column=0, sticky="e", padx=4)
        self.room_cb = ttk.Combobox(box, textvariable=self.room, state="readonly", width=28)
        self.room_cb.grid(row=0, column=1, sticky="w")
        self.v = form(box, [("category", "Category", "combo", services.MAINT_CATEGORIES),
                            ("description", "Description", "entry"),
                            ("reported_date", "Reported date", "entry"),
                            ("assigned_to", "Assigned staff/vendor", "entry"), ("cost", "Cost", "entry"),
                            ("status", "Status", "combo", services.MAINT_STATUSES)], 1)
        self.clear()
        bar = ttk.Frame(box)
        bar.grid(row=8, column=0, columnspan=2)
        self.buttons(bar, [("Add", self.add), ("Update selected", self.update), ("Delete selected", self.delete),
                           ("Clear", self.clear), ("Export CSV", self.table.export)])

    def clear(self):
        for var in self.v.values():
            var.set("")
        self.room.set("")
        self.v["reported_date"].set(today_str())
        self.v["status"].set("Open")

    def on_select(self, _):
        r = self.table.selected()
        if r:
            for k, var in self.v.items():
                var.set("" if r.get(k) is None else r[k])
            self.room.set(r["room_no"] or "")

    def collect(self):
        d = {k: v.get() for k, v in self.v.items()}
        d["room_id"] = self.room_map.get(self.room.get())
        return d

    @guard
    def add(self):
        self.svc.save_maintenance(self.collect())
        self.app.refresh_all()

    @guard
    def update(self):
        r = self.table.selected()
        if not r:
            raise ValidationError("Select a record first.")
        self.svc.save_maintenance(self.collect(), r["id"])
        self.app.refresh_all()

    @guard
    def delete(self):
        r = self.table.selected()
        if not r:
            raise ValidationError("Select a record first.")
        if messagebox.askyesno("Delete", "Delete this maintenance record?"):
            self.svc.delete_maintenance(r["id"])
            self.app.refresh_all()

    def refresh(self):
        self.room_cb["values"] = self.room_choices()
        self.table.load(self.svc.list_maintenance())


class ExpensesTab(Tab):
    def __init__(self, *a):
        super().__init__(*a)
        self.table = Table(self, [("expense_date", "Date", 90), ("category", "Category", 110),
                                  ("description", "Description", 280), ("amount", "Amount", 90)],
                           "expenses", height=12)
        self.table.pack(fill="both", expand=True)
        self.table.tree.bind("<<TreeviewSelect>>", self.on_select)
        box = ttk.LabelFrame(self, text="Expense", padding=6)
        box.pack(fill="x")
        self.v = form(box, [("expense_date", "Date", "entry"),
                            ("category", "Category", "combo", services.EXPENSE_CATEGORIES),
                            ("description", "Description", "entry"), ("amount", "Amount", "entry")])
        self.v["expense_date"].set(today_str())
        bar = ttk.Frame(box)
        bar.grid(row=4, column=0, columnspan=2)
        self.buttons(bar, [("Add", self.add), ("Update selected", self.update), ("Delete selected", self.delete),
                           ("Export CSV", self.table.export)])

    def on_select(self, _):
        r = self.table.selected()
        if r:
            for k, var in self.v.items():
                var.set(r[k])

    @guard
    def add(self):
        self.svc.save_expense({k: v.get() for k, v in self.v.items()})
        self.v["amount"].set("")
        self.v["description"].set("")
        self.app.refresh_all()

    @guard
    def update(self):
        r = self.table.selected()
        if not r:
            raise ValidationError("Select an expense first.")
        self.svc.save_expense({k: v.get() for k, v in self.v.items()}, r["id"])
        self.app.refresh_all()

    @guard
    def delete(self):
        r = self.table.selected()
        if not r:
            raise ValidationError("Select an expense first.")
        if messagebox.askyesno("Delete", "Delete this expense?"):
            self.svc.delete_expense(r["id"])
            self.app.refresh_all()

    def refresh(self):
        self.table.load(self.svc.list_expenses())


class VisitorsTab(Tab):
    def __init__(self, *a):
        super().__init__(*a)
        self.table = Table(self, [("name", "Visitor", 130), ("phone", "Phone", 100),
                                  ("resident_name", "Visiting", 130), ("room_no", "Room", 60),
                                  ("check_in", "Check-in", 120), ("check_out", "Check-out", 120)],
                           "visitors", height=12)
        self.table.pack(fill="both", expand=True)
        box = ttk.LabelFrame(self, text="Visitor entry", padding=6)
        box.pack(fill="x")
        self.resident = tk.StringVar()
        ttk.Label(box, text="Resident visited").grid(row=0, column=0, sticky="e", padx=4)
        self.res_cb = ttk.Combobox(box, textvariable=self.resident, state="readonly", width=34)
        self.res_cb.grid(row=0, column=1, sticky="w")
        self.v = form(box, [("name", "Visitor name", "entry"), ("phone", "Visitor phone", "entry"),
                            ("check_in", "Check-in (YYYY-MM-DD HH:MM)", "entry")], 1)
        self.v["check_in"].set(now_str())
        bar = ttk.Frame(box)
        bar.grid(row=4, column=0, columnspan=2)
        self.buttons(bar, [("Add visitor", self.add), ("Check out selected", self.checkout),
                           ("Export CSV", self.table.export)])

    @guard
    def add(self):
        d = {k: v.get() for k, v in self.v.items()}
        d["resident_id"] = self.res_map.get(self.resident.get())
        self.svc.add_visitor(d)
        self.v["name"].set("")
        self.v["phone"].set("")
        self.v["check_in"].set(now_str())
        self.app.refresh_all()

    @guard
    def checkout(self):
        r = self.table.selected()
        if not r:
            raise ValidationError("Select a visitor first.")
        self.svc.visitor_checkout(r["id"])
        self.app.refresh_all()

    def refresh(self):
        self.res_map = {f"{r['name']} (Room {r['room_no']})": r["id"] for r in self.svc.list_residents("Active")}
        self.res_cb["values"] = list(self.res_map)
        self.table.load(self.svc.list_visitors())


class ReportsTab(Tab):
    def __init__(self, *a):
        super().__init__(*a)
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Month (YYYY-MM):").pack(side="left")
        self.month = tk.StringVar(value=current_month())
        ttk.Entry(top, textvariable=self.month, width=10).pack(side="left", padx=4)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left")
        self.summary = tk.StringVar()
        ttk.Label(self, textvariable=self.summary, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=4)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        spec = {
            "Occupancy": [("room_no", "Room", 70), ("capacity", "Beds", 60), ("occupied", "Occupied", 80),
                          ("vacant", "Vacant", 70), ("residents", "Residents", 400)],
            "Payments": [("receipt_no", "Receipt", 90), ("resident_name", "Resident", 140), ("month", "Month", 70),
                         ("amount", "Amount", 90), ("payment_date", "Paid on", 90), ("method", "Method", 70)],
            "Pending rent": [("name", "Resident", 140), ("room_no", "Room", 60), ("months_due", "Months", 60),
                             ("total_due", "Due", 90), ("total_paid", "Paid", 90),
                             ("outstanding", "Outstanding", 90)],
            "Expenses": [("category", "Category", 140), ("entries", "Entries", 70), ("total", "Total", 100)],
            "Maintenance": [("room_no", "Room", 60), ("category", "Category", 90),
                            ("description", "Description", 220), ("reported_date", "Reported", 90),
                            ("assigned_to", "Assigned", 100), ("cost", "Cost", 80), ("status", "Status", 90)],
        }
        self.tables = {}
        for name, cols in spec.items():
            frame = ttk.Frame(nb)
            t = Table(frame, cols, "report_" + name.lower().replace(" ", "_"), height=12)
            t.pack(fill="both", expand=True)
            ttk.Button(frame, text="Export CSV", command=t.export).pack(anchor="w")
            nb.add(frame, text=name)
            self.tables[name] = t

    @guard
    def refresh(self):
        from .utils import parse_month
        month = parse_month(self.month.get(), "Month")
        s = self.svc.income_vs_expense(month)
        self.summary.set(f"{month}: income {s['income']:,.2f} | expenses {s['expenses']:,.2f} | net {s['net']:,.2f}")
        self.tables["Occupancy"].load(self.svc.room_occupancy())
        self.tables["Payments"].load(self.svc.list_payments(month))
        self.tables["Pending rent"].load(self.svc.pending_rent())
        self.tables["Expenses"].load(self.svc.expense_summary(month))
        self.tables["Maintenance"].load(self.svc.list_maintenance())


class LoginWindow(tk.Tk):
    def __init__(self, svc):
        super().__init__()
        self.svc, self.ok = svc, False
        self.title("Gents Hostel Manager - Admin Login")
        self.resizable(False, False)
        f = ttk.Frame(self, padding=20)
        f.pack()
        ttk.Label(f, text="Gents Hostel Manager", font=("Segoe UI", 16, "bold")).grid(columnspan=2, pady=8)
        self.v = form(f, [("username", "Username", "entry"), ("password", "Password", "password")], 1)
        self.v["username"].set(db.DEFAULT_USERNAME)
        ttk.Button(f, text="Login", command=self.submit).grid(columnspan=2, pady=10)
        self.bind("<Return>", lambda _: self.submit())

    def submit(self):
        if self.svc.login(self.v["username"].get(), self.v["password"].get()):
            self.username = self.v["username"].get().strip()
            self.ok = True
            self.destroy()
        else:
            messagebox.showerror("Login failed", "Incorrect username or password.")


class MainApp(tk.Tk):
    def __init__(self, svc, username):
        super().__init__()
        self.svc, self.username = svc, username
        self.title("Gents Hostel Manager")
        self.geometry("1000x720")
        bar = ttk.Frame(self, padding=4)
        bar.pack(fill="x")
        ttk.Button(bar, text="Backup database", command=self.backup).pack(side="left", padx=4)
        ttk.Button(bar, text="Change password", command=self.change_password).pack(side="left", padx=4)
        ttk.Label(bar, text=f"Data folder: {db.data_dir()}").pack(side="right")
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)
        self.tabs = []
        for title, cls in [("Dashboard", DashboardTab), ("Rooms & Beds", RoomsTab), ("Residents", ResidentsTab),
                           ("Rent", RentTab), ("Maintenance", MaintenanceTab), ("Expenses", ExpensesTab),
                           ("Visitors", VisitorsTab), ("Reports", ReportsTab)]:
            tab = cls(self.nb, svc, self)
            self.nb.add(tab, text=title)
            self.tabs.append(tab)
        self.nb.bind("<<NotebookTabChanged>>", lambda _: self.nb.nametowidget(self.nb.select()).refresh())
        self.refresh_all()

    def refresh_all(self):
        for t in self.tabs:
            t.refresh()

    @guard
    def backup(self):
        folder = filedialog.askdirectory(title="Select backup folder (e.g. USB drive)")
        if folder:
            target = db.backup_database(self.svc.conn, folder)
            messagebox.showinfo("Backup complete", f"Backup saved to:\n{target}")

    def change_password(self):
        win = tk.Toplevel(self)
        win.title("Change password")
        f = ttk.Frame(win, padding=14)
        f.pack()
        v = form(f, [("old", "Current password", "password"), ("new", "New password", "password"),
                     ("confirm", "Confirm new password", "password")])

        @guard
        def save():
            self.svc.change_password(self.username, v["old"].get(), v["new"].get(), v["confirm"].get())
            messagebox.showinfo("Password changed", "Your password has been updated.")
            win.destroy()
        ttk.Button(f, text="Save", command=save).grid(columnspan=2, pady=8)


def run():
    conn = db.connect()
    db.init_db(conn)
    svc = Service(conn)
    login = LoginWindow(svc)
    login.mainloop()
    if login.ok:
        MainApp(svc, login.username).mainloop()
    conn.close()
