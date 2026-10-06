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
    
    # 1. Donor Table
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
    
    conn.commit()
    
    # Seed default demo accounts if empty
    cur.execute("SELECT COUNT(*) FROM donor")
    if cur.fetchone()[0] == 0:
        seed_data(conn)
        
    conn.close()

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
    donor1_id = cur.lastrowid
    
    # Seed NGOs
    cur.execute('''
        INSERT INTO ngo (ngo_name, contact_no, address, capacity, priority_level)
        VALUES 
        ('Hope Haven Shelter', '+1 555-0888', '78 Community Way', 150, 'High'),
        ('Food For All Foundation', '+1 555-0777', '34 Hope Ave', 300, 'High')
    ''')
    
    # Seed Volunteers
    cur.execute('''
        INSERT INTO volunteer (name, contact_no, vehicle_type, availability_status)
        VALUES 
        ('Alex Rivera', '+1 555-0333', 'Bike', 'Available'),
        ('Sarah Jenkins', '+1 555-0444', 'Van', 'Available')
    ''')
    
    # Seed Sample Donation
    cur.execute('''
        INSERT INTO food_donation (food_type, quantity, original_quantity, accepted_quantity, donation_status, time, date_of_donation, donor_id)
        VALUES 
        ('Fresh Vegetable Rice & Curry', 35, 35, 0, 'Pending', '22:00', %s, %s)
    ''' % (f"'{today_str}'", donor1_id))
    
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
