import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'food_db.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    # Enable WAL mode for better concurrency
    cur.execute("PRAGMA journal_mode=WAL")
    
    # 1. Donor Table (original columns preserved, new ones added via ALTER TABLE below)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS donor (
            donor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_name TEXT UNIQUE NOT NULL,
            donor_type TEXT DEFAULT 'Individual',
            contact_no TEXT,
            address TEXT,
            hygiene_rating REAL DEFAULT 0.0,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'donor',
            email TEXT,
            registration_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. NGO Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ngo (
            ngo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ngo_name TEXT UNIQUE NOT NULL,
            contact_no TEXT,
            address TEXT,
            capacity INTEGER DEFAULT 0,
            priority_level TEXT DEFAULT 'Medium'
        )
    ''')
    
    # 3. Volunteer Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS volunteer (
            volunteer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            contact_no TEXT,
            vehicle_type TEXT DEFAULT 'Bike',
            availability_status TEXT DEFAULT 'Available'
        )
    ''')
    
    # 4. Food Donation Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS food_donation (
            donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            original_quantity INTEGER NOT NULL,
            accepted_quantity INTEGER DEFAULT 0,
            donation_status TEXT DEFAULT 'Pending',
            time TEXT,
            date_of_donation TEXT,
            donor_id INTEGER,
            parent_donation_id INTEGER DEFAULT NULL,
            FOREIGN KEY (donor_id) REFERENCES donor (donor_id)
        )
    ''')
    
    # 5. Pickup Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS pickup (
            pickup_id INTEGER PRIMARY KEY AUTOINCREMENT,
            time DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Pending',
            otp_code TEXT,
            donation_id INTEGER,
            volunteer_id INTEGER,
            FOREIGN KEY (donation_id) REFERENCES food_donation (donation_id),
            FOREIGN KEY (volunteer_id) REFERENCES volunteer (volunteer_id)
        )
    ''')
    
    # 6. Delivery Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS delivery (
            delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
            time DATETIME DEFAULT CURRENT_TIMESTAMP,
            receiver_name TEXT,
            delivery_status TEXT DEFAULT 'Pending',
            pickup_id INTEGER,
            ngo_id INTEGER,
            FOREIGN KEY (pickup_id) REFERENCES pickup (pickup_id),
            FOREIGN KEY (ngo_id) REFERENCES ngo (ngo_id)
        )
    ''')
    
    # 7. Feedback Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            donation_id INTEGER,
            donor_id INTEGER,
            ngo_id INTEGER,
            rating INTEGER DEFAULT 5,
            comments TEXT,
            hygiene_score INTEGER DEFAULT 5,
            feedback_date TEXT,
            from_ngo INTEGER DEFAULT 1,
            FOREIGN KEY (donation_id) REFERENCES food_donation (donation_id),
            FOREIGN KEY (donor_id) REFERENCES donor (donor_id),
            FOREIGN KEY (ngo_id) REFERENCES ngo (ngo_id)
        )
    ''')

    # ─────────────────────────────────────────────────────────────
    # 8. Admin Table (NEW)
    # ─────────────────────────────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS admin_user (
            admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ─────────────────────────────────────────────────────────────
    # 9. Donor Verification Table (NEW)
    # ─────────────────────────────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS donor_verification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_id INTEGER UNIQUE NOT NULL,
            fssai_number TEXT,
            fssai_cert_path TEXT,
            verification_status TEXT DEFAULT 'Pending',
            rejection_reason TEXT,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reviewed_at DATETIME,
            FOREIGN KEY (donor_id) REFERENCES donor(donor_id)
        )
    ''')

    # ─────────────────────────────────────────────────────────────
    # 10. NGO Verification Table (NEW)
    # ─────────────────────────────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ngo_verification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ngo_id INTEGER UNIQUE NOT NULL,
            darpan_id TEXT,
            reg_cert_path TEXT,
            reg_type TEXT,
            reg_12a TEXT,
            reg_80g TEXT,
            contact_person TEXT,
            contact_phone TEXT,
            verification_status TEXT DEFAULT 'Pending',
            rejection_reason TEXT,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reviewed_at DATETIME,
            FOREIGN KEY (ngo_id) REFERENCES ngo(ngo_id)
        )
    ''')

    # ─────────────────────────────────────────────────────────────
    # 11. Volunteer Verification Table (NEW)
    # ─────────────────────────────────────────────────────────────
    cur.execute('''
        CREATE TABLE IF NOT EXISTS volunteer_verification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            volunteer_id INTEGER UNIQUE NOT NULL,
            photo_id_path TEXT,
            selfie_path TEXT,
            vehicle_reg_no TEXT,
            dl_path TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            verification_status TEXT DEFAULT 'Pending',
            rejection_reason TEXT,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reviewed_at DATETIME,
            FOREIGN KEY (volunteer_id) REFERENCES volunteer(volunteer_id)
        )
    ''')

    conn.commit()

    # ─────────────────────────────────────────────────────────────
    # Safe ALTER TABLE migrations for food_donation
    # (adds columns if they don't already exist)
    # ─────────────────────────────────────────────────────────────
    _safe_add_column(cur, 'food_donation', 'cooked_at', 'TEXT')
    _safe_add_column(cur, 'food_donation', 'food_category', "TEXT DEFAULT 'Vegetarian'")
    _safe_add_column(cur, 'food_donation', 'food_photo_path', 'TEXT')

    # Safe ALTER for donor (add donor_type if needed, email if needed etc.)
    _safe_add_column(cur, 'donor', 'donor_type', "TEXT DEFAULT 'Individual'")
    
    # Safe ALTER for ngo (add password + email for proper login)
    _safe_add_column(cur, 'ngo', 'password', 'TEXT')
    _safe_add_column(cur, 'ngo', 'email', 'TEXT')

    # Safe ALTER for volunteer (add password + email)
    _safe_add_column(cur, 'volunteer', 'password', 'TEXT')
    _safe_add_column(cur, 'volunteer', 'email', 'TEXT')

    conn.commit()
    
    # Seed default demo accounts if donor table is empty
    cur.execute("SELECT COUNT(*) FROM donor")
    if cur.fetchone()[0] == 0:
        seed_data(conn)

    # Seed default admin if not present
    cur.execute("SELECT COUNT(*) FROM admin_user")
    if cur.fetchone()[0] == 0:
        seed_admin(conn)

    # Initialize Rewards & Recognition Schema
    try:
        from rewards_service import init_rewards_schema, sync_existing_records
        init_rewards_schema(conn)
        sync_existing_records(conn)
    except Exception as e:
        print(f"[Rewards Schema] Error initializing rewards: {e}")
        
    conn.close()


def _safe_add_column(cur, table, column, column_def):
    """Adds a column to a table only if it doesn't already exist."""
    cur.execute(f"PRAGMA table_info({table})")
    existing = [row['name'] for row in cur.fetchall()]
    if column not in existing:
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
        except Exception as e:
            print(f"[Migration] Could not add {column} to {table}: {e}")


def seed_admin(conn):
    """Seed a default admin account with bcrypt hash."""
    import hashlib
    cur = conn.cursor()
    # Default admin: username=admin, password=FoodBridgeAdmin2026!
    # We store a SHA-256 hash (no bcrypt dependency needed)
    pw_hash = hashlib.sha256("FoodBridgeAdmin2026!".encode()).hexdigest()
    cur.execute(
        "INSERT INTO admin_user (username, password_hash) VALUES (?, ?)",
        ("admin", pw_hash)
    )
    conn.commit()


def seed_data(conn):
    cur = conn.cursor()
    today_str = date.today().strftime('%Y-%m-%d')
    
    # Seed Donors
    cur.execute('''
        INSERT INTO donor (donor_name, donor_type, contact_no, address, hygiene_rating, password, role, email)
        VALUES 
        ('Fresh Bites Bakery', 'Restaurant', '+1 555-0192', '124 Market St, Downtown', 4.8, 'donor123', 'donor', 'contact@freshbites.com'),
        ('Grand Plaza Hotel', 'Hotel', '+1 555-0144', '500 Ocean Drive', 4.5, 'donor123', 'donor', 'kitchen@grandplaza.com')
    ''')
    donor1_id = cur.lastrowid - 1  # first inserted donor id

    # Actually get the real IDs
    cur.execute("SELECT donor_id FROM donor ORDER BY donor_id ASC LIMIT 1")
    row = cur.fetchone()
    donor1_id = row['donor_id'] if row else 1
    
    # Seed NGOs
    cur.execute('''
        INSERT INTO ngo (ngo_name, contact_no, address, capacity, priority_level, password, email)
        VALUES 
        ('Hope Haven Shelter', '+1 555-0888', '78 Community Way', 150, 'High', 'ngo123', 'hope@haven.org'),
        ('Food For All Foundation', '+1 555-0777', '34 Hope Ave', 300, 'High', 'ngo123', 'info@foodforall.org')
    ''')
    
    # Seed Volunteers
    cur.execute('''
        INSERT INTO volunteer (name, contact_no, vehicle_type, availability_status, password, email)
        VALUES 
        ('Alex Rivera', '+1 555-0333', 'Bike', 'Available', 'vol123', 'alex@email.com'),
        ('Sarah Jenkins', '+1 555-0444', 'Van', 'Available', 'vol123', 'sarah@email.com')
    ''')
    
    # Seed Sample Donation
    cur.execute('''
        INSERT INTO food_donation (food_type, quantity, original_quantity, accepted_quantity, donation_status, time, date_of_donation, donor_id, food_category)
        VALUES 
        ('Fresh Vegetable Rice & Curry', 35, 35, 0, 'Pending', '22:00', ?, ?, 'Vegetarian')
    ''', (today_str, donor1_id))
    
    conn.commit()

def expire_donations_db(conn):
    """
    Marks Pending donations as Wasted when:
      - The donation date is before today, OR
      - The donation date is today and available-until time has passed.
    """
    cur = conn.cursor()
    now = datetime.now()
    today_str = date.today().strftime('%Y-%m-%d')
    current_time_str = now.strftime('%H:%M:%S')

    cur.execute('''
        UPDATE food_donation
        SET donation_status = 'Wasted'
        WHERE donation_status = 'Pending'
          AND time IS NOT NULL
          AND (
            date_of_donation < ?
            OR
            (date_of_donation = ? AND time < ?)
          )
    ''', (today_str, today_str, current_time_str))
    conn.commit()
