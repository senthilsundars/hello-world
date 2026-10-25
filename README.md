# hello-world
This repository is for practicing the GitHub Flow.

## Gents Hostel Manager

An offline Windows desktop application (Python, Tkinter, SQLite) for managing a single gents hostel.
Used only by the warden/manager: no internet and no resident logins.

### Prerequisites
- Windows 10/11 (also runs on Linux/macOS for development)
- Python 3.9+ from python.org (the installer includes Tkinter; keep "tcl/tk and IDLE" ticked)
- No third-party packages are needed.

### Install and run
```
git clone https://github.com/senthilsundars/hello-world.git
cd hello-world
python run_hostel_manager.py
```
(`python -m hostel_manager` also works.) Run tests with `python -m unittest discover -s hostel_manager/tests -t .`

### Login
Default development credentials: **admin / admin123**. Change the password via the **Change password**
button in the main window. If you forget it, move `hostel.db` out of the data folder to start fresh with the default credentials (all data in it is then not loaded; keep it as a backup).

### Features
- **Dashboard**: total rooms/beds, occupied/vacant beds, this-month collection, outstanding rent, open maintenance.
- **Rooms & Beds**: 30 seeded rooms (101-130, 3 beds each); add/edit/delete rooms and capacities; occupancy view.
- **Residents**: add, edit, check out; name, phone, address, ID proof, emergency contact, join date, rent,
  deposit, room/bed. Only free beds are selectable and occupied beds are rejected.
- **Rent**: record payments (month, amount, date, Cash/UPI/Bank), automatic receipt numbers (RCPT-00001...),
  outstanding rent = (months from join month to current month) x monthly rent - total paid.
- **Maintenance**, **Expenses**, **Visitors**: registers with the fields requested; statuses Open/In Progress/Completed.
- **Reports**: occupancy, payments, pending rent, expenses summary, maintenance, plus income vs expense for a month.
  Every table has an **Export CSV** button (opens in Excel).
- Dates are stored as `YYYY-MM-DD` (visitor times `YYYY-MM-DD HH:MM`); months as `YYYY-MM`.

### Data location
Windows: `%LOCALAPPDATA%\GentsHostelManager\hostel.db`; other systems: `~/.gents_hostel_manager/`.
Set the `HOSTEL_DATA_DIR` environment variable to use another folder. Set `HOSTEL_NAME` to change the name printed on receipts.

### Printing receipts
After saving a payment, a receipt HTML file is created in `<data folder>\receipts\RCPT-xxxxx.html` and opened in your
default browser, which shows the print dialog (or press Ctrl+P). Choose your printer or "Save as PDF".
Use **Print selected receipt** to reprint an old one.

### Backup
Click **Backup database**, choose a folder or USB drive; a timestamped `hostel_backup_YYYYMMDD_HHMMSS.db` is written.
To restore, close the app and copy a backup over `hostel.db` in the data folder.

### Packaging as .exe
```
pip install pyinstaller
pyinstaller --onefile --windowed --name GentsHostelManager run_hostel_manager.py
```
The executable appears in `dist\`. The database stays in the data folder, so upgrading the exe keeps your data.

### Manual test steps
1. Run the app and log in with admin / admin123 (a wrong password shows an error).
2. Dashboard shows 30 rooms / 90 beds / 0 occupied.
3. Residents: add a resident in room 101 bed 1 (try blank name or rent "abc" for validation errors); try a second resident on the same bed - rejected.
4. Rent: record a payment; the receipt opens in the browser; check outstanding rent updates on Dashboard and Reports.
5. Add maintenance, expense and visitor entries; check visitor out.
6. Reports: view tabs and export a CSV. Click **Backup database** and verify the file.
7. Check out the resident; the bed becomes vacant.
