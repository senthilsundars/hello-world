"""Printable HTML receipts."""
import html
import os
import webbrowser
from pathlib import Path

from . import db

HOSTEL_NAME = os.environ.get("HOSTEL_NAME", "Gents Hostel")


def render_receipt(p, hostel_name=HOSTEL_NAME):
    e = lambda v: html.escape(str(v if v is not None else ""))
    rows = [("Receipt No", p["receipt_no"]), ("Payment Date", p["payment_date"]),
            ("Received From", p["resident_name"]),
            ("Room / Bed", f"{p.get('room_no') or '-'} / {p.get('bed_no') or '-'}"),
            ("Rent For Month", p["month"]), ("Payment Method", p["method"])]
    if p.get("notes"):
        rows.append(("Notes", p["notes"]))
    body = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in rows)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Receipt {e(p['receipt_no'])}</title>
<style>
@page {{ size: A4; margin: 20mm; }}
body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 30px auto; }}
h1 {{ text-align: center; margin-bottom: 0; }} h2 {{ text-align: center; margin-top: 4px; font-weight: normal; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
th, td {{ border: 1px solid #444; padding: 8px; text-align: left; }} th {{ width: 40%; background: #eee; }}
.amount {{ font-size: 1.4em; font-weight: bold; }} .sign {{ margin-top: 60px; text-align: right; }}
</style></head><body onload="window.print()">
<h1>{e(hostel_name)}</h1><h2>Rent Receipt</h2>
<table>{body}<tr><th>Amount Received</th><td class="amount">Rs. {p['amount']:,.2f}</td></tr></table>
<div class="sign">Authorised Signature</div>
</body></html>"""


def save_receipt(payment, folder=None):
    folder = Path(folder) if folder else db.data_dir() / "receipts"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{payment['receipt_no']}.html"
    path.write_text(render_receipt(payment), encoding="utf-8")
    return path


def open_receipt(path):
    """Open the receipt in the default browser (it auto-opens the print dialog)."""
    webbrowser.open(Path(path).resolve().as_uri())
