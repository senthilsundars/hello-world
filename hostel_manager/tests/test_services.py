import tempfile
import unittest
from pathlib import Path

from hostel_manager import db, receipts
from hostel_manager.services import Service, export_csv
from hostel_manager.utils import ValidationError, current_month, today_str


def resident(**kw):
    d = dict(name="Ravi", phone="9876543210", address="Chennai", id_proof_type="Aadhaar",
             id_proof_number="1234", emergency_name="Mom", emergency_phone="9123456780",
             join_date=today_str(), monthly_rent="3000", deposit="5000", room_id=1, bed_no=1)
    d.update(kw)
    return d


class ResidentPhotoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.conn = db.connect(self.root / "t.db")
        db.init_db(self.conn)
        self.s = Service(self.conn, self.root)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def image(self, name="face.png", data=b"img"):
        path = self.root / name
        path.write_bytes(data)
        return str(path)

    def add(self, **kw):
        self.s.save_resident(resident(**kw))
        return self.s.list_residents()[0]

    def test_upload_copies_photo(self):
        src = self.image()
        r = self.add(photo_source=src)
        stored = self.s.photo_file(r["photo_path"])
        self.assertTrue(r["photo_path"].startswith("resident_photos/"))
        self.assertEqual(stored.read_bytes(), b"img")
        self.assertNotEqual(stored, Path(src))
        Path(src).unlink()
        self.assertTrue(stored.is_file())

    def test_unique_names_no_overwrite(self):
        src = self.image()
        a = self.add(photo_source=src)
        self.s.save_resident(resident(name="B", bed_no=2, photo_source=src))
        paths = {x["photo_path"] for x in self.s.list_residents()}
        self.assertEqual(len(paths), 2)
        self.assertEqual(a["photo_path"] in paths, True)

    def test_edit_retains_and_replaces_photo(self):
        r = self.add(photo_source=self.image())
        old = self.s.photo_file(r["photo_path"])
        self.s.save_resident(resident(name="Renamed"), r["id"])
        kept = self.s.get_resident(r["id"])
        self.assertEqual(kept["photo_path"], r["photo_path"])
        self.assertTrue(old.is_file())
        self.s.save_resident(resident(photo_source=self.image("new.jpg", b"new")), r["id"])
        new = self.s.get_resident(r["id"])
        self.assertNotEqual(new["photo_path"], r["photo_path"])
        self.assertFalse(old.exists())
        self.assertEqual(self.s.photo_file(new["photo_path"]).read_bytes(), b"new")

    def test_clear_removes_file_checkout_keeps(self):
        r = self.add(photo_source=self.image())
        stored = self.s.photo_file(r["photo_path"])
        self.s.checkout_resident(r["id"])
        self.assertTrue(stored.is_file())
        self.assertEqual(self.s.get_resident(r["id"])["photo_path"], r["photo_path"])
        self.s.save_resident(resident(name="C", bed_no=2, photo_source=self.image("c.png")))
        c = [x for x in self.s.list_residents("Active")][0]
        cstored = self.s.photo_file(c["photo_path"])
        self.s.clear_resident_photo(c["id"])
        self.assertFalse(cstored.exists())
        self.assertIsNone(self.s.get_resident(c["id"])["photo_path"])

    def test_invalid_input(self):
        with self.assertRaises(ValidationError):
            self.s.save_resident(resident(photo_source=str(self.root / "missing.png")))
        with self.assertRaises(ValidationError):
            self.s.save_resident(resident(photo_source=self.image("doc.txt")))
        self.assertEqual(self.s.list_residents(), [])
        self.assertFalse(self.s.photo_dir.exists() and any(self.s.photo_dir.iterdir()))

    def test_upgrade_existing_database(self):
        old = db.connect(self.root / "old.db")
        old.executescript(db.SCHEMA.replace(", photo_path TEXT", ""))
        self.assertNotIn("photo_path", [r[1] for r in old.execute("PRAGMA table_info(residents)")])
        db.init_db(old)
        db.init_db(old)
        self.assertIn("photo_path", [r[1] for r in old.execute("PRAGMA table_info(residents)")])
        old.close()


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        db.init_db(self.conn)
        self.s = Service(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_seed_and_login(self):
        self.assertEqual(len(self.s.list_rooms()), 30)
        self.assertTrue(self.s.login("admin", "admin123"))
        self.assertFalse(self.s.login("admin", "bad"))
        self.s.change_password("admin", "admin123", "newpass1", "newpass1")
        self.assertTrue(self.s.login("admin", "newpass1"))

    def test_occupied_bed_rejected(self):
        self.s.save_resident(resident())
        with self.assertRaises(ValidationError):
            self.s.save_resident(resident(name="Other"))
        self.s.save_resident(resident(name="Other", bed_no=2))
        self.assertEqual(self.s.dashboard()["occupied_beds"], 2)

    def test_validation(self):
        with self.assertRaises(ValidationError):
            self.s.save_resident(resident(name=""))
        with self.assertRaises(ValidationError):
            self.s.save_resident(resident(monthly_rent="abc"))
        with self.assertRaises(ValidationError):
            self.s.save_resident(resident(join_date="01/02/2025"))
        with self.assertRaises(ValidationError):
            self.s.save_resident(resident(bed_no=9))

    def test_checkout_frees_bed_and_edit(self):
        self.s.save_resident(resident())
        rid = self.s.list_residents()[0]["id"]
        self.s.save_resident(resident(name="Ravi K"), rid)  # same bed edit allowed
        self.s.checkout_resident(rid)
        self.s.save_resident(resident(name="New"))
        self.assertEqual(self.s.dashboard()["occupied_beds"], 1)

    def test_company_details_optional_and_editable(self):
        self.s.save_resident(resident())
        r = self.s.list_residents()[0]
        self.assertEqual((r["company_name"], r["company_address"]), ("", ""))
        self.s.save_resident(resident(company_name="  Acme Ltd ", company_address=" 1 Main St "), r["id"])
        r = self.s.get_resident(r["id"])
        self.assertEqual((r["company_name"], r["company_address"]), ("Acme Ltd", "1 Main St"))
        self.s.save_resident(resident(name="Ravi K"), r["id"])  # omitted keys are preserved
        self.assertEqual(self.s.get_resident(r["id"])["company_name"], "Acme Ltd")
        self.s.save_resident(resident(company_name="", company_address=""), r["id"])
        self.assertEqual(self.s.get_resident(r["id"])["company_address"], "")

    def test_migration_adds_company_columns(self):
        path = Path(self.tmp.name) / "old.db"
        old = db.connect(path)
        old.executescript(db.SCHEMA.replace(
            ",\n    company_name TEXT NOT NULL DEFAULT '', company_address TEXT NOT NULL DEFAULT ''", ""))
        old.execute("INSERT INTO rooms(room_no, capacity) VALUES ('1', 3)")
        old.execute("INSERT INTO residents(name, phone, address, id_proof_type, id_proof_number, emergency_name,"
                    " emergency_phone, join_date, monthly_rent, room_id, bed_no) VALUES"
                    " ('Old','9876543210','x','Aadhaar','1','m','9123456780','2024-01-01',1000,1,1)")
        old.commit()
        db.init_db(old)
        row = Service(old).list_residents()[0]
        self.assertEqual((row["name"], row["company_name"]), ("Old", ""))
        old.close()

    def test_rent_and_receipt(self):
        self.s.save_resident(resident())
        rid = self.s.list_residents()[0]["id"]
        self.assertEqual(self.s.dashboard()["outstanding_rent"], 3000)
        pid = self.s.record_payment(rid, current_month(), "1000", today_str(), "UPI")
        self.assertEqual(self.s.dashboard()["outstanding_rent"], 2000)
        self.assertEqual(self.s.dashboard()["month_collection"], 1000)
        with self.assertRaises(ValidationError):
            self.s.record_payment(rid, "2025-13", "10", today_str(), "Cash")
        with self.assertRaises(ValidationError):
            self.s.record_payment(rid, current_month(), "10", today_str(), "Cheque")
        p = self.s.get_payment(pid)
        self.assertEqual(p["receipt_no"], "RCPT-00001")
        path = receipts.save_receipt(p, self.tmp.name)
        self.assertIn("RCPT-00001", path.read_text(encoding="utf-8"))

    def test_other_modules_and_csv(self):
        self.s.save_maintenance(dict(room_id=1, category="Plumbing", description="Leak",
                                     reported_date=today_str(), status="Open", cost="0"))
        self.assertEqual(self.s.dashboard()["open_maintenance"], 1)
        with self.assertRaises(ValidationError):
            self.s.save_expense(dict(expense_date=today_str(), category="Water", amount="x"))
        self.s.save_expense(dict(expense_date=today_str(), category="Water", amount="500"))
        self.assertEqual(self.s.income_vs_expense(current_month())["net"], -500)
        self.s.add_visitor(dict(name="Guest", room_id=1, check_in="2025-01-01 10:00"))
        vid = self.s.list_visitors()[0]["id"]
        with self.assertRaises(ValidationError):
            self.s.visitor_checkout(vid, "2025-01-01 09:00")
        self.s.visitor_checkout(vid, "2025-01-01 11:00")
        out = Path(self.tmp.name) / "e.csv"
        export_csv(out, self.s.list_expenses(), [("expense_date", "Date"), ("amount", "Amount")])
        self.assertIn("500", out.read_text(encoding="utf-8-sig"))

    def test_backup(self):
        target = db.backup_database(self.conn, self.tmp.name)
        self.assertTrue(target.exists())
        c2 = db.connect(target)
        self.assertEqual(c2.execute("SELECT COUNT(*) FROM rooms").fetchone()[0], 30)
        c2.close()


if __name__ == "__main__":
    unittest.main()
