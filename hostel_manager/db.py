"""SQLite connection, schema, seed data and backup."""
import hashlib
import hmac
import os
import secrets
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_NAME = "hostel.db"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin123"
SEED_ROOMS = 30
SEED_CAPACITY = 3


def data_dir():
    """Folder holding the database, receipts and exports.

    Override with the HOSTEL_DATA_DIR environment variable.
    """
    override = os.environ.get("HOSTEL_DATA_DIR")
    if override:
        path = Path(override)
    elif sys.platform.startswith("win"):
        path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "GentsHostelManager"
    else:
        path = Path.home() / ".gents_hostel_manager"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path():
    return data_dir() / DB_NAME


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
    salt TEXT NOT NULL, password_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY, room_no TEXT UNIQUE NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0));
CREATE TABLE IF NOT EXISTS residents (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL,
    address TEXT NOT NULL, id_proof_type TEXT NOT NULL, id_proof_number TEXT NOT NULL,
    emergency_name TEXT NOT NULL, emergency_phone TEXT NOT NULL,
    join_date TEXT NOT NULL, monthly_rent REAL NOT NULL, deposit REAL NOT NULL DEFAULT 0,
    room_id INTEGER REFERENCES rooms(id), bed_no INTEGER,
    status TEXT NOT NULL DEFAULT 'Active', checkout_date TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_bed
    ON residents(room_id, bed_no) WHERE status = 'Active';
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY, resident_id INTEGER NOT NULL REFERENCES residents(id),
    month TEXT NOT NULL, amount REAL NOT NULL, payment_date TEXT NOT NULL,
    method TEXT NOT NULL, receipt_no TEXT UNIQUE NOT NULL, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS maintenance (
    id INTEGER PRIMARY KEY, room_id INTEGER REFERENCES rooms(id),
    category TEXT NOT NULL, description TEXT NOT NULL, reported_date TEXT NOT NULL,
    assigned_to TEXT DEFAULT '', cost REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Open');
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY, expense_date TEXT NOT NULL, category TEXT NOT NULL,
    description TEXT DEFAULT '', amount REAL NOT NULL);
CREATE TABLE IF NOT EXISTS visitors (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT DEFAULT '',
    resident_id INTEGER REFERENCES residents(id), room_id INTEGER REFERENCES rooms(id),
    check_in TEXT NOT NULL, check_out TEXT DEFAULT '');
"""


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def set_password(conn, username, password):
    salt = secrets.token_hex(16)
    h = hash_password(password, salt)
    cur = conn.execute("UPDATE users SET salt=?, password_hash=? WHERE username=?", (salt, h, username))
    if cur.rowcount == 0:
        conn.execute("INSERT INTO users(username, salt, password_hash) VALUES (?,?,?)", (username, salt, h))
    conn.commit()


def verify_password(conn, username, password):
    row = conn.execute("SELECT salt, password_hash FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        return False
    return hmac.compare_digest(hash_password(password, row["salt"]), row["password_hash"])


def connect(path=None):
    conn = sqlite3.connect(str(path or db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    """Create tables and seed default admin and 30 rooms on first run."""
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        set_password(conn, DEFAULT_USERNAME, DEFAULT_PASSWORD)
    if conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO rooms(room_no, capacity) VALUES (?,?)",
            [(f"{100 + i}", SEED_CAPACITY) for i in range(1, SEED_ROOMS + 1)],
        )
    conn.commit()


def backup_database(conn, dest_folder):
    """Write a consistent copy of the database into dest_folder; returns its path."""
    dest = Path(dest_folder)
    if not dest.is_dir():
        raise FileNotFoundError(f"Backup folder does not exist: {dest}")
    target = dest / f"hostel_backup_{datetime.now():%Y%m%d_%H%M%S}.db"
    out = sqlite3.connect(str(target))
    try:
        conn.backup(out)
    finally:
        out.close()
    return target
