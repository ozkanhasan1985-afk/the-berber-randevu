#!/usr/bin/env python3
import json
import os
import re
import sqlite3
import unicodedata
import uuid
from base64 import b64encode
from datetime import date, datetime, timedelta
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "the_berber.sqlite"
ADMIN_PIN = os.environ.get("THE_BERBER_ADMIN_PIN", "19071903")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()
THE_BERBER_NOTIFY_WHATSAPP_TO = os.environ.get("THE_BERBER_NOTIFY_WHATSAPP_TO", "").strip()

SERVICES = [
    {"id": "haircut", "name": "Saç Kesimi", "duration": 45, "price": 650},
    {"id": "beard", "name": "Sakal Tasarımı", "duration": 30, "price": 420},
    {"id": "full-care", "name": "Full Bakım", "duration": 75, "price": 980},
    {"id": "groom", "name": "Damat Paketi", "duration": 110, "price": 1450},
    {"id": "skin-care", "name": "Yüz Bakımı", "duration": 40, "price": 520},
]

BARBERS = [
    {"id": "hasan-ozkan", "name": "Hasan Özkan", "title": "Usta berber"},
]

DEFAULT_CONTACT = {
    "title": "THE BERBER Kadıköy",
    "address": "Bağdat Caddesi No: 124, Kadıköy / İstanbul",
    "phone": "+905551112233",
    "email": "randevu@theberber.com",
    "whatsapp": "+905551112233",
    "instagram": "theberber",
}

OPEN_TIME = "07:00"
CLOSE_TIME = "23:30"
SLOT_STEP_MINUTES = 30


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                service_id TEXT NOT NULL,
                barber_id TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                duration INTEGER NOT NULL,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS barbers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                title TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS services (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                duration INTEGER NOT NULL,
                price INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(date);
            CREATE INDEX IF NOT EXISTS idx_appointments_customer ON appointments(customer_id);
            CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
            """
        )
        timestamp = now_iso()
        existing_barbers = conn.execute("SELECT COUNT(*) AS total FROM barbers WHERE active = 1").fetchone()["total"]
        if existing_barbers == 0:
            conn.executemany(
                """
                INSERT INTO barbers (id, name, title, active, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    title = excluded.title,
                    active = 1,
                    updated_at = excluded.updated_at
                """,
                [(barber["id"], barber["name"], barber["title"], timestamp, timestamp) for barber in BARBERS],
            )
        existing_services = conn.execute("SELECT COUNT(*) AS total FROM services").fetchone()["total"]
        if existing_services == 0:
            conn.executemany(
                """
                INSERT INTO services (id, name, duration, price, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                [
                    (service["id"], service["name"], service["duration"], service["price"], timestamp, timestamp)
                    for service in SERVICES
                ],
            )
        conn.executemany(
            """
            INSERT OR IGNORE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            """,
            [(key, value, timestamp) for key, value in DEFAULT_CONTACT.items()],
        )


def now_iso():
    return datetime.now().replace(microsecond=0).isoformat()


def row_to_dict(row):
    return dict(row) if row is not None else None


def active_default_signature():
    return {
        "services": [
            {"id": service["id"], "name": service["name"], "duration": service["duration"], "price": service["price"]}
            for service in SERVICES
        ],
        "barbers": [{"id": barber["id"], "name": barber["name"], "title": barber["title"]} for barber in BARBERS],
        "contact": dict(DEFAULT_CONTACT),
    }


def state_snapshot():
    return {
        "services": [
            {"id": service["id"], "name": service["name"], "duration": service["duration"], "price": service["price"]}
            for service in list_services(active_only=True)
        ],
        "barbers": [
            {"id": barber["id"], "name": barber["name"], "title": barber["title"]}
            for barber in list_barbers(active_only=True)
        ],
        "contact": get_contact(),
    }


def clean_phone(phone):
    return re.sub(r"\s+", " ", str(phone or "").strip())


def whatsapp_address(value):
    number = str(value or "").strip()
    if not number:
        return ""
    if number.startswith("whatsapp:"):
        return number
    return f"whatsapp:{number}"


def whatsapp_notifications_configured():
    return all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, THE_BERBER_NOTIFY_WHATSAPP_TO])


def whatsapp_notification_status():
    missing = []
    if not TWILIO_ACCOUNT_SID:
        missing.append("TWILIO_ACCOUNT_SID")
    if not TWILIO_AUTH_TOKEN:
        missing.append("TWILIO_AUTH_TOKEN")
    if not TWILIO_WHATSAPP_FROM:
        missing.append("TWILIO_WHATSAPP_FROM")
    if not THE_BERBER_NOTIFY_WHATSAPP_TO:
        missing.append("THE_BERBER_NOTIFY_WHATSAPP_TO")
    return {
        "provider": "twilio",
        "enabled": len(missing) == 0,
        "missing": missing,
        "to": whatsapp_address(THE_BERBER_NOTIFY_WHATSAPP_TO) if THE_BERBER_NOTIFY_WHATSAPP_TO else "",
    }


def send_whatsapp_notification(booking):
    if not whatsapp_notifications_configured() or not booking:
        return {"sent": False, "skipped": True}

    body = "\n".join(
        [
            "THE BERBER yeni randevu",
            f"Müşteri: {booking.get('customer_name', '-')}",
            f"Telefon: {booking.get('phone', '-')}",
            f"Hizmet: {booking.get('service_name', '-')}",
            f"Berber: {booking.get('barber_name', '-')}",
            f"Tarih/Saat: {booking.get('date', '-')} {booking.get('time', '-')}",
            f"Kod: {booking.get('id', '-')}",
        ]
    )
    payload = urlencode(
        {
            "From": whatsapp_address(TWILIO_WHATSAPP_FROM),
            "To": whatsapp_address(THE_BERBER_NOTIFY_WHATSAPP_TO),
            "Body": body,
        }
    ).encode("utf-8")
    auth = b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode("utf-8")).decode("ascii")
    request = Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
        data=payload,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=12) as response:
            response.read()
        return {"sent": True, "skipped": False}
    except URLError as exc:
        print(f"[THE BERBER] WhatsApp bildirimi gönderilemedi: {exc}")
        return {"sent": False, "skipped": False, "error": str(exc)}


def list_services(active_only=True):
    where = "WHERE active = 1" if active_only else ""
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, name, duration, price, active, created_at, updated_at
            FROM services
            {where}
            ORDER BY active DESC, name COLLATE NOCASE ASC
            """
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def service_by_id(service_id, active_only=True):
    if not service_id:
        return None
    where = "AND active = 1" if active_only else ""
    with connect() as conn:
        row = conn.execute(
            f"SELECT id, name, duration, price, active FROM services WHERE id = ? {where}",
            (service_id,),
        ).fetchone()
    return row_to_dict(row)


def parse_positive_int(payload, key, label):
    try:
        value = int(str(payload.get(key, "")).strip())
    except ValueError as exc:
        raise ValueError(f"{label} sayı olmalı.") from exc
    if value <= 0:
        raise ValueError(f"{label} sıfırdan büyük olmalı.")
    return value


def create_service(payload):
    name = str(payload.get("name", "")).strip()
    duration = parse_positive_int(payload, "duration", "Süre")
    price = parse_positive_int(payload, "price", "Fiyat")
    if len(name) < 2:
        raise ValueError("Hizmet adı zorunlu.")

    base_id = slugify_name(name)
    service_id = base_id
    timestamp = now_iso()
    with connect() as conn:
        index = 2
        while conn.execute("SELECT 1 FROM services WHERE id = ?", (service_id,)).fetchone():
            service_id = f"{base_id}-{index}"
            index += 1
        conn.execute(
            """
            INSERT INTO services (id, name, duration, price, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (service_id, name, duration, price, timestamp, timestamp),
        )
    return service_by_id(service_id, active_only=False)


def update_service(service_id, payload):
    name = str(payload.get("name", "")).strip()
    duration = parse_positive_int(payload, "duration", "Süre")
    price = parse_positive_int(payload, "price", "Fiyat")
    if len(name) < 2:
        raise ValueError("Hizmet adı zorunlu.")

    timestamp = now_iso()
    with connect() as conn:
        result = conn.execute(
            """
            UPDATE services
            SET name = ?, duration = ?, price = ?, updated_at = ?
            WHERE id = ?
            """,
            (name, duration, price, timestamp, service_id),
        )
    if result.rowcount == 0:
        return None
    return service_by_id(service_id, active_only=False)


def deactivate_service(service_id):
    timestamp = now_iso()
    with connect() as conn:
        result = conn.execute(
            "UPDATE services SET active = 0, updated_at = ? WHERE id = ?",
            (timestamp, service_id),
        )
    if result.rowcount == 0:
        return None
    return service_by_id(service_id, active_only=False)


def get_contact():
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    contact = dict(DEFAULT_CONTACT)
    contact.update({row["key"]: row["value"] for row in rows if row["key"] in DEFAULT_CONTACT})
    return contact


def update_contact(payload):
    contact = {}
    for key in DEFAULT_CONTACT:
        value = str(payload.get(key, "")).strip()
        if key in {"title", "address"} and len(value) < 2:
            raise ValueError("İletişim başlığı ve adres zorunlu.")
        contact[key] = value

    timestamp = now_iso()
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            [(key, value, timestamp) for key, value in contact.items()],
        )
    return get_contact()


def list_barbers(active_only=True):
    where = "WHERE active = 1" if active_only else ""
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, name, title, active, created_at, updated_at
            FROM barbers
            {where}
            ORDER BY active DESC, name COLLATE NOCASE ASC
            """
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def barber_by_id(barber_id, active_only=True):
    if not barber_id:
        return None
    where = "AND active = 1" if active_only else ""
    with connect() as conn:
        row = conn.execute(
            f"SELECT id, name, title, active FROM barbers WHERE id = ? {where}",
            (barber_id,),
        ).fetchone()
    return row_to_dict(row)


def slugify_name(name):
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or uuid.uuid4().hex[:8]


def clean_record_id(value, fallback):
    record_id = str(value or "").strip().lower()
    if re.fullmatch(r"[a-z0-9-]+", record_id):
        return record_id
    return slugify_name(fallback)


def create_barber(payload):
    name = str(payload.get("name", "")).strip()
    title = str(payload.get("title", "")).strip() or "Berber"
    if len(name) < 2:
        raise ValueError("Berber adı zorunlu.")

    base_id = slugify_name(name)
    barber_id = base_id
    timestamp = now_iso()
    with connect() as conn:
        index = 2
        while conn.execute("SELECT 1 FROM barbers WHERE id = ?", (barber_id,)).fetchone():
            barber_id = f"{base_id}-{index}"
            index += 1
        conn.execute(
            """
            INSERT INTO barbers (id, name, title, active, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            (barber_id, name, title, timestamp, timestamp),
        )
    return barber_by_id(barber_id, active_only=False)


def deactivate_barber(barber_id):
    timestamp = now_iso()
    with connect() as conn:
        result = conn.execute(
            "UPDATE barbers SET active = 0, updated_at = ? WHERE id = ?",
            (timestamp, barber_id),
        )
    if result.rowcount == 0:
        return None
    return barber_by_id(barber_id, active_only=False)


def restore_site_state(payload):
    services = payload.get("services", [])
    barbers = payload.get("barbers", [])
    contact_payload = payload.get("contact", {})
    if not isinstance(services, list) or not isinstance(barbers, list) or not isinstance(contact_payload, dict):
        raise ValueError("Yedek verisi geçersiz.")
    if not services or not barbers:
        raise ValueError("Yedekte en az bir hizmet ve bir berber olmalı.")

    clean_services = []
    for service in services:
        if not isinstance(service, dict):
            raise ValueError("Hizmet yedek verisi geçersiz.")
        name = str(service.get("name", "")).strip()
        if len(name) < 2:
            raise ValueError("Hizmet adı zorunlu.")
        clean_services.append(
            {
                "id": clean_record_id(service.get("id"), name),
                "name": name,
                "duration": parse_positive_int(service, "duration", "Süre"),
                "price": parse_positive_int(service, "price", "Fiyat"),
            }
        )

    clean_barbers = []
    for barber in barbers:
        if not isinstance(barber, dict):
            raise ValueError("Berber yedek verisi geçersiz.")
        name = str(barber.get("name", "")).strip()
        title = str(barber.get("title", "")).strip() or "Berber"
        if len(name) < 2:
            raise ValueError("Berber adı zorunlu.")
        clean_barbers.append({"id": clean_record_id(barber.get("id"), name), "name": name, "title": title})

    clean_contact = {}
    for key, default in DEFAULT_CONTACT.items():
        value = str(contact_payload.get(key, default)).strip()
        if key in {"title", "address"} and len(value) < 2:
            raise ValueError("İletişim başlığı ve adres zorunlu.")
        clean_contact[key] = value

    timestamp = now_iso()
    with connect() as conn:
        conn.execute("UPDATE services SET active = 0, updated_at = ?", (timestamp,))
        conn.executemany(
            """
            INSERT INTO services (id, name, duration, price, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                duration = excluded.duration,
                price = excluded.price,
                active = 1,
                updated_at = excluded.updated_at
            """,
            [
                (service["id"], service["name"], service["duration"], service["price"], timestamp, timestamp)
                for service in clean_services
            ],
        )
        conn.execute("UPDATE barbers SET active = 0, updated_at = ?", (timestamp,))
        conn.executemany(
            """
            INSERT INTO barbers (id, name, title, active, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                title = excluded.title,
                active = 1,
                updated_at = excluded.updated_at
            """,
            [(barber["id"], barber["name"], barber["title"], timestamp, timestamp) for barber in clean_barbers],
        )
        conn.executemany(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            [(key, value, timestamp) for key, value in clean_contact.items()],
        )

    return state_snapshot()


def parse_minutes(value):
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def format_minutes(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def appointment_with_names(row):
    item = row_to_dict(row)
    if not item:
        return None
    service = service_by_id(item["service_id"], active_only=False)
    barber = barber_by_id(item["barber_id"], active_only=False)
    item["service_name"] = service["name"] if service else item["service_id"]
    item["barber_name"] = barber["name"] if barber else item["barber_id"]
    return item


def get_available_slots(day, barber_id, service_id):
    service = service_by_id(service_id)
    barber = barber_by_id(barber_id)
    if not service or not barber:
        raise ValueError("Hizmet veya berber bulunamadı.")

    try:
        selected_day = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Geçerli bir gün seç.") from exc

    today = date.today()
    current_time = datetime.now().time()
    now_minutes = current_time.hour * 60 + current_time.minute
    start = parse_minutes(OPEN_TIME)
    end = parse_minutes(CLOSE_TIME)
    service_duration = service["duration"]

    with connect() as conn:
        busy_rows = conn.execute(
            """
            SELECT time, duration FROM appointments
            WHERE date = ? AND barber_id = ? AND status NOT IN ('cancelled', 'no_show')
            """,
            (day, barber_id),
        ).fetchall()

    busy = []
    for row in busy_rows:
        busy_start = parse_minutes(row["time"])
        busy.append((busy_start, busy_start + int(row["duration"])))

    slots = []
    current = start
    while current <= end:
        slot_end = current + service_duration
        is_past = selected_day < today
        is_earlier_today = selected_day == today and current <= now_minutes
        overlaps = any(current < busy_end and slot_end > busy_start for busy_start, busy_end in busy)
        if not is_past and not is_earlier_today and not overlaps:
            slots.append(format_minutes(current))
        current += SLOT_STEP_MINUTES
    return slots


def find_or_create_customer(payload):
    name = str(payload.get("name", "")).strip()
    phone = clean_phone(payload.get("phone"))
    email = str(payload.get("email", "")).strip().lower()
    notes = str(payload.get("customer_notes", "")).strip()
    if len(name) < 2:
        raise ValueError("Ad soyad zorunlu.")
    if len(phone) < 10:
        raise ValueError("Telefon numarası eksik görünüyor.")

    timestamp = now_iso()
    with connect() as conn:
        existing = conn.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE customers
                SET name = ?, email = COALESCE(NULLIF(?, ''), email), notes = COALESCE(NULLIF(?, ''), notes), updated_at = ?
                WHERE id = ?
                """,
                (name, email, notes, timestamp, existing["id"]),
            )
            return existing["id"]

        customer_id = uuid.uuid4().hex[:12]
        conn.execute(
            """
            INSERT INTO customers (id, name, phone, email, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (customer_id, name, phone, email, notes, timestamp, timestamp),
        )
        return customer_id


def create_booking(payload):
    service = service_by_id(payload.get("service_id"))
    barber = barber_by_id(payload.get("barber_id"))
    day = str(payload.get("date", "")).strip()
    selected_time = str(payload.get("time", "")).strip()
    note = str(payload.get("note", "")).strip()
    if not service:
        raise ValueError("Hizmet seç.")
    if not barber:
        raise ValueError("Berber seç.")
    if selected_time not in get_available_slots(day, barber["id"], service["id"]):
        raise ValueError("Bu saat artık uygun değil. Lütfen başka bir saat seç.")

    customer_id = find_or_create_customer(payload)
    timestamp = now_iso()
    appointment_id = uuid.uuid4().hex[:10].upper()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO appointments (
                id, customer_id, service_id, barber_id, date, time, duration,
                status, source, note, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 'website', ?, ?, ?)
            """,
            (
                appointment_id,
                customer_id,
                service["id"],
                barber["id"],
                day,
                selected_time,
                service["duration"],
                note,
                timestamp,
                timestamp,
            ),
        )
    booking = get_booking(appointment_id)
    send_whatsapp_notification(booking)
    return booking


def get_booking(appointment_id):
    with connect() as conn:
        row = conn.execute(
            """
            SELECT a.*, c.name AS customer_name, c.phone, c.email, c.notes AS customer_notes
            FROM appointments a
            JOIN customers c ON c.id = a.customer_id
            WHERE a.id = ?
            """,
            (appointment_id,),
        ).fetchone()
    return appointment_with_names(row)


def list_bookings(params):
    filters = []
    values = []
    day = params.get("date", [""])[0]
    status = params.get("status", [""])[0]
    query = params.get("q", [""])[0].strip()

    if day:
        filters.append("a.date = ?")
        values.append(day)
    if status and status != "all":
        filters.append("a.status = ?")
        values.append(status)
    if query:
        filters.append("(c.name LIKE ? OR c.phone LIKE ? OR a.id LIKE ?)")
        like = f"%{query}%"
        values.extend([like, like, like])

    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT a.*, c.name AS customer_name, c.phone, c.email, c.notes AS customer_notes
            FROM appointments a
            JOIN customers c ON c.id = a.customer_id
            {where}
            ORDER BY a.date ASC, a.time ASC
            LIMIT 300
            """,
            values,
        ).fetchall()
    return [appointment_with_names(row) for row in rows]


def list_customers(params):
    query = params.get("q", [""])[0].strip()
    values = []
    where = ""
    if query:
        where = "WHERE c.name LIKE ? OR c.phone LIKE ? OR c.email LIKE ?"
        like = f"%{query}%"
        values = [like, like, like]

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT
                c.*,
                COUNT(a.id) AS appointment_count,
                MAX(a.date || ' ' || a.time) AS last_visit
            FROM customers c
            LEFT JOIN appointments a ON a.customer_id = c.id
            {where}
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT 300
            """,
            values,
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def get_summary():
    today = date.today().isoformat()
    with connect() as conn:
        today_count = conn.execute(
            "SELECT COUNT(*) AS total FROM appointments WHERE date = ? AND status NOT IN ('cancelled', 'no_show')",
            (today,),
        ).fetchone()["total"]
        pending_count = conn.execute(
            "SELECT COUNT(*) AS total FROM appointments WHERE status = 'pending'"
        ).fetchone()["total"]
        customer_count = conn.execute("SELECT COUNT(*) AS total FROM customers").fetchone()["total"]
        upcoming_count = conn.execute(
            "SELECT COUNT(*) AS total FROM appointments WHERE date >= ? AND status NOT IN ('cancelled', 'completed', 'no_show')",
            (today,),
        ).fetchone()["total"]
    return {
        "today": today_count,
        "pending": pending_count,
        "customers": customer_count,
        "upcoming": upcoming_count,
    }


def update_booking(appointment_id, payload):
    allowed_statuses = {"pending", "confirmed", "completed", "cancelled", "no_show"}
    status = payload.get("status")
    note = payload.get("note")
    fields = []
    values = []
    if status:
        if status not in allowed_statuses:
            raise ValueError("Geçersiz durum.")
        fields.append("status = ?")
        values.append(status)
    if note is not None:
        fields.append("note = ?")
        values.append(str(note).strip())
    if not fields:
        raise ValueError("Güncellenecek alan yok.")
    fields.append("updated_at = ?")
    values.append(now_iso())
    values.append(appointment_id)

    with connect() as conn:
        conn.execute(f"UPDATE appointments SET {', '.join(fields)} WHERE id = ?", values)
    return get_booking(appointment_id)


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def log_message(self, format, *args):
        print(f"[THE BERBER] {self.address_string()} - {format % args}")

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status=400):
        self.send_json({"error": message}, status)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def require_admin(self):
        if self.headers.get("X-Admin-Pin") == ADMIN_PIN:
            return True
        self.send_error_json("Yönetici PIN'i gerekli.", 401)
        return False

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        try:
            if path == "/api/bootstrap":
                self.send_json(
                    {
                        "services": list_services(active_only=True),
                        "barbers": list_barbers(active_only=True),
                        "contact": get_contact(),
                        "settings": {"open": OPEN_TIME, "close": CLOSE_TIME, "slotStep": SLOT_STEP_MINUTES},
                    }
                )
            elif path == "/api/slots":
                slots = get_available_slots(
                    params.get("date", [""])[0],
                    params.get("barber_id", [""])[0],
                    params.get("service_id", [""])[0],
                )
                self.send_json({"slots": slots})
            elif path == "/api/admin/summary":
                if self.require_admin():
                    self.send_json(get_summary())
            elif path == "/api/admin/bookings":
                if self.require_admin():
                    self.send_json({"bookings": list_bookings(params)})
            elif path == "/api/admin/customers":
                if self.require_admin():
                    self.send_json({"customers": list_customers(params)})
            elif path == "/api/admin/barbers":
                if self.require_admin():
                    self.send_json({"barbers": list_barbers(active_only=True)})
            elif path == "/api/admin/services":
                if self.require_admin():
                    self.send_json({"services": list_services(active_only=True)})
            elif path == "/api/admin/contact":
                if self.require_admin():
                    self.send_json({"contact": get_contact()})
            elif path == "/api/admin/state":
                if self.require_admin():
                    self.send_json({"state": state_snapshot(), "defaultState": active_default_signature()})
            elif path == "/api/admin/notifications":
                if self.require_admin():
                    self.send_json({"whatsapp": whatsapp_notification_status()})
            elif path == "/admin":
                self.path = "/admin.html"
                super().do_GET()
            else:
                super().do_GET()
        except ValueError as exc:
            self.send_error_json(str(exc), 422)
        except Exception as exc:
            self.send_error_json(f"Beklenmeyen hata: {exc}", 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/bookings":
                booking = create_booking(self.read_json())
                self.send_json({"booking": booking}, 201)
            elif parsed.path == "/api/admin/barbers":
                if not self.require_admin():
                    return
                barber = create_barber(self.read_json())
                self.send_json({"barber": barber}, 201)
            elif parsed.path == "/api/admin/services":
                if not self.require_admin():
                    return
                service = create_service(self.read_json())
                self.send_json({"service": service}, 201)
            elif parsed.path == "/api/admin/state/restore":
                if not self.require_admin():
                    return
                self.send_json(restore_site_state(self.read_json()))
            else:
                self.send_error_json("Adres bulunamadı.", 404)
        except json.JSONDecodeError:
            self.send_error_json("Geçersiz veri.", 400)
        except ValueError as exc:
            self.send_error_json(str(exc), 422)
        except Exception as exc:
            self.send_error_json(f"Beklenmeyen hata: {exc}", 500)

    def do_PATCH(self):
        if not self.require_admin():
            return
        try:
            parsed = urlparse(self.path)
            booking_match = re.fullmatch(r"/api/admin/bookings/([A-F0-9]+)", parsed.path)
            service_match = re.fullmatch(r"/api/admin/services/([a-z0-9-]+)", parsed.path)
            if booking_match:
                booking = update_booking(booking_match.group(1), self.read_json())
                if not booking:
                    self.send_error_json("Randevu bulunamadı.", 404)
                    return
                self.send_json({"booking": booking})
                return
            if service_match:
                service = update_service(service_match.group(1), self.read_json())
                if not service:
                    self.send_error_json("Hizmet bulunamadı.", 404)
                    return
                self.send_json({"service": service})
                return
            if parsed.path == "/api/admin/contact":
                self.send_json({"contact": update_contact(self.read_json())})
                return
            self.send_error_json("Adres bulunamadı.", 404)
        except json.JSONDecodeError:
            self.send_error_json("Geçersiz veri.", 400)
        except ValueError as exc:
            self.send_error_json(str(exc), 422)
        except Exception as exc:
            self.send_error_json(f"Beklenmeyen hata: {exc}", 500)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        barber_match = re.fullmatch(r"/api/admin/barbers/([a-z0-9-]+)", parsed.path)
        service_match = re.fullmatch(r"/api/admin/services/([a-z0-9-]+)", parsed.path)
        if not barber_match and not service_match:
            self.send_error_json("Adres bulunamadı.", 404)
            return
        if not self.require_admin():
            return
        try:
            if barber_match:
                barber = deactivate_barber(barber_match.group(1))
                if not barber:
                    self.send_error_json("Berber bulunamadı.", 404)
                    return
                self.send_json({"barber": barber})
                return
            service = deactivate_service(service_match.group(1))
            if not service:
                self.send_error_json("Hizmet bulunamadı.", 404)
                return
            self.send_json({"service": service})
        except Exception as exc:
            self.send_error_json(f"Beklenmeyen hata: {exc}", 500)


def run():
    init_db()
    port = int(os.environ.get("PORT", "8010"))
    host = os.environ.get("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"THE BERBER randevu sistemi: http://{host}:{port}")
    print(f"Yönetim paneli: http://{host}:{port}/admin")
    server.serve_forever()


if __name__ == "__main__":
    run()
