import os
import sys
import random
from datetime import datetime, date
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_cors import CORS
from database import get_db, init_db, expire_donations_db

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'foodbridge_mobile_secret_key_2026'
CORS(app, supports_credentials=True)

# Initialize Database Schema & Seed Data
init_db()

def run_expiry(conn):
    try:
        expire_donations_db(conn)
    except Exception as e:
        print("Expiry error:", e)

# ═════════════════════════════════════════════════════════════
# PAGE ROUTE
# ═════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')

# ═════════════════════════════════════════════════════════════
# AUTH ROUTES
# ═════════════════════════════════════════════════════════════

@app.route('/do_login', methods=['POST'])
def do_login():
    data = request.get_json() if request.is_json else request.form
    name = data.get('name', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'donor').strip().lower()

    if not name or not password:
        return jsonify({"success": False, "error": "Please fill in all fields"}), 400

    conn = get_db()
    cur = conn.cursor()

    if role == 'donor':
        cur.execute("SELECT donor_id, donor_name, password FROM donor WHERE LOWER(TRIM(donor_name)) = LOWER(TRIM(?))", (name,))
        user = cur.fetchone()
        conn.close()
        if not user:
            return jsonify({"success": False, "error": "Donor not found."}), 404
        if str(user['password']).strip() != password:
            return jsonify({"success": False, "error": "Incorrect password."}), 401
        session.clear()
        session['user_id'] = user['donor_id']
        session['user_name'] = user['donor_name']
        session['role'] = 'donor'
        return jsonify({"success": True, "role": "donor", "user_name": user['donor_name']})

    elif role == 'ngo':
        cur.execute("SELECT ngo_id, ngo_name FROM ngo WHERE LOWER(TRIM(ngo_name)) = LOWER(TRIM(?))", (name,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return jsonify({"success": False, "error": "NGO not found."}), 404
        session.clear()
        session['user_id'] = row['ngo_id']
        session['user_name'] = row['ngo_name']
        session['role'] = 'ngo'
        return jsonify({"success": True, "role": "ngo", "user_name": row['ngo_name']})

    elif role == 'volunteer':
        cur.execute("SELECT volunteer_id, name FROM volunteer WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))", (name,))
        vol = cur.fetchone()
        conn.close()
        if not vol:
            return jsonify({"success": False, "error": "Volunteer not found."}), 404
        session.clear()
        session['user_id'] = vol['volunteer_id']
        session['user_name'] = vol['name']
        session['role'] = 'volunteer'
        return jsonify({"success": True, "role": "volunteer", "user_name": vol['name']})

    conn.close()
    return jsonify({"success": False, "error": "Invalid role."}), 400

@app.route('/do_signup', methods=['POST'])
def do_signup():
    data = request.get_json() if request.is_json else request.form
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    mobile = data.get('mobile', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'donor').strip().lower()

    if not name or not password or not email:
        return jsonify({"success": False, "error": "Please fill in all required fields."}), 400

    conn = get_db()
    cur = conn.cursor()

    if role == 'donor':
        cur.execute("SELECT donor_id FROM donor WHERE LOWER(TRIM(donor_name)) = LOWER(TRIM(?))", (name,))
        if cur.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "Donor name already exists."}), 400
        cur.execute(
            "INSERT INTO donor (donor_name, donor_type, contact_no, address, hygiene_rating, password, role, email) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, 'Individual', mobile, '', 5.0, password, 'donor', email)
        )
        donor_id = cur.lastrowid
        conn.commit()
        conn.close()
        session.clear()
        session['user_id'] = donor_id
        session['user_name'] = name
        session['role'] = 'donor'
        return jsonify({"success": True, "role": "donor", "user_name": name})

    elif role == 'volunteer':
        cur.execute("SELECT volunteer_id FROM volunteer WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))", (name,))
        if cur.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "Volunteer name already exists."}), 400
        cur.execute(
            "INSERT INTO volunteer (name, contact_no, vehicle_type, availability_status) VALUES (?, ?, ?, ?)",
            (name, mobile, 'Bike', 'Available')
        )
        vol_id = cur.lastrowid
        conn.commit()
        conn.close()
        session.clear()
        session['user_id'] = vol_id
        session['user_name'] = name
        session['role'] = 'volunteer'
        return jsonify({"success": True, "role": "volunteer", "user_name": name})

    elif role == 'ngo':
        address = data.get('address', '')
        capacity_raw = str(data.get('capacity', '')).strip()
        capacity = int(capacity_raw) if capacity_raw.isdigit() else 100
        priority = data.get('priority', 'Medium')
        cur.execute("SELECT ngo_id FROM ngo WHERE LOWER(TRIM(ngo_name)) = LOWER(TRIM(?))", (name,))
        if cur.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "NGO name already exists."}), 400
        cur.execute(
            "INSERT INTO ngo (ngo_name, contact_no, address, capacity, priority_level) VALUES (?, ?, ?, ?, ?)",
            (name, mobile, address, capacity, priority)
        )
        ngo_id = cur.lastrowid
        conn.commit()
        conn.close()
        session.clear()
        session['user_id'] = ngo_id
        session['user_name'] = name
        session['role'] = 'ngo'
        return jsonify({"success": True, "role": "ngo", "user_name": name})

    conn.close()
    return jsonify({"success": False, "error": "Invalid role."}), 400

@app.route('/logout')
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route('/api/me')
def me():
    if 'user_id' not in session:
        return jsonify({"authenticated": False}), 200
    return jsonify({
        "authenticated": True,
        "user_id": session['user_id'],
        "user_name": session['user_name'],
        "role": session['role']
    })

# ═════════════════════════════════════════════════════════════
# API — DONOR ENDPOINTS
# ═════════════════════════════════════════════════════════════

@app.route('/api/donor/profile')
def donor_profile():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT donor_name, contact_no, address, hygiene_rating, email FROM donor WHERE donor_id=?", (session['user_id'],))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "donor_name": row['donor_name'],
        "contact_no": row['contact_no'],
        "address": row['address'],
        "hygiene_rating": float(row['hygiene_rating'] or 0.0),
        "email": row['email']
    })

@app.route('/api/donor/update', methods=['POST'])
def update_donor_profile():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({"error": "Unauthorized"}), 401
    d = request.get_json()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE donor SET donor_name=?, contact_no=?, address=?, email=? WHERE donor_id=?",
        (d.get('donor_name'), d.get('contact_no'), d.get('address'), d.get('email'), session['user_id'])
    )
    conn.commit()
    conn.close()
    session['user_name'] = d.get('donor_name')
    return jsonify({"success": True, "message": "Profile updated"})

@app.route('/api/donor/stats')
def donor_stats():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    run_expiry(conn)
    cur = conn.cursor()
    uid = session['user_id']
    cur.execute("SELECT COUNT(*) FROM food_donation WHERE donor_id=?", (uid,))
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM food_donation WHERE donor_id=? AND donation_status='Pending'", (uid,))
    pending = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM food_donation WHERE donor_id=? AND donation_status='Accepted'", (uid,))
    accepted = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM food_donation WHERE donor_id=? AND donation_status='Completed'", (uid,))
    completed = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM food_donation WHERE donor_id=? AND donation_status='Wasted'", (uid,))
    wasted = cur.fetchone()[0]
    conn.close()
    return jsonify({
        "success": True,
        "stats": {
            "total": total, "pending": pending, "accepted": accepted,
            "completed": completed, "wasted": wasted
        }
    })

@app.route('/api/donor/donations')
def donor_own_donations():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    run_expiry(conn)
    cur = conn.cursor()
    cur.execute("""
        SELECT fd.donation_id, fd.food_type, fd.quantity, fd.donation_status,
               fd.time, fd.date_of_donation,
               fd.original_quantity, fd.accepted_quantity,
               p.status       AS pickup_status,
               p.otp_code,
               v.name         AS volunteer_name,
               v.contact_no   AS volunteer_contact,
               dl.delivery_status,
               n.ngo_name
        FROM food_donation fd
        LEFT JOIN pickup    p  ON p.donation_id  = fd.donation_id
        LEFT JOIN volunteer v  ON v.volunteer_id = p.volunteer_id
        LEFT JOIN delivery  dl ON dl.pickup_id   = p.pickup_id
        LEFT JOIN ngo       n  ON n.ngo_id        = dl.ngo_id
        WHERE fd.donor_id = ?
          AND fd.donation_status != 'Wasted'
        ORDER BY fd.donation_id DESC
    """, (session['user_id'],))
    rows = cur.fetchall()
    conn.close()
    data = []
    for r in rows:
        data.append({
            "donation_id": r['donation_id'], "food_type": r['food_type'],
            "quantity": r['quantity'], "donation_status": r['donation_status'],
            "time": str(r['time']) if r['time'] else None,
            "date_of_donation": str(r['date_of_donation']) if r['date_of_donation'] else None,
            "original_quantity": r['original_quantity'],
            "accepted_quantity": r['accepted_quantity'],
            "pickup_status": r['pickup_status'], "otp_code": r['otp_code'],
            "volunteer_name": r['volunteer_name'], "volunteer_contact": r['volunteer_contact'],
            "delivery_status": r['delivery_status'], "ngo_name": r['ngo_name']
        })
    return jsonify({"success": True, "data": data})

@app.route('/api/donor/wasted-donations')
def donor_wasted_donations():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    run_expiry(conn)
    cur = conn.cursor()
    cur.execute("""
        SELECT fd.donation_id, fd.food_type, fd.quantity,
               fd.time, fd.date_of_donation,
               fd.original_quantity, fd.accepted_quantity
        FROM food_donation fd
        WHERE fd.donor_id = ?
          AND fd.donation_status = 'Wasted'
        ORDER BY fd.donation_id DESC
    """, (session['user_id'],))
    rows = cur.fetchall()
    conn.close()
    data = []
    for r in rows:
        data.append({
            "donation_id": r['donation_id'], "food_type": r['food_type'],
            "quantity": r['quantity'],
            "available_until": str(r['time']) if r['time'] else None,
            "date_of_donation": str(r['date_of_donation']) if r['date_of_donation'] else None,
            "original_quantity": r['original_quantity'],
            "accepted_quantity": r['accepted_quantity']
        })
    return jsonify({"success": True, "data": data})

@app.route('/api/donor/feedback-received', methods=['GET'])
def donor_feedback_received():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT f.feedback_id, f.rating, f.comments, f.hygiene_score, f.feedback_date,
               fd.food_type, n.ngo_name
        FROM feedback f
        JOIN food_donation fd ON f.donation_id = fd.donation_id
        JOIN ngo n ON f.ngo_id = n.ngo_id
        WHERE f.donor_id = ? AND f.from_ngo = 1
        ORDER BY f.feedback_id DESC
    """, (session['user_id'],))
    rows = cur.fetchall()
    conn.close()
    data = []
    for r in rows:
        data.append({
            "feedback_id": r['feedback_id'], "rating": r['rating'], "comments": r['comments'],
            "hygiene_score": r['hygiene_score'], "feedback_date": str(r['feedback_date']) if r['feedback_date'] else None,
            "food_type": r['food_type'], "ngo_name": r['ngo_name']
        })
    return jsonify({"success": True, "data": data})

@app.route('/api/donations', methods=['POST'])
def create_donation():
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({"error": "Unauthorized"}), 401
    d = request.get_json()
    if not d:
        return jsonify({"error": "No data received"}), 400
    quantity = d.get('quantity')
    if quantity is None or str(quantity).strip() == "":
        return jsonify({"error": "Quantity is required"}), 400
    try:
        quantity = int(quantity)
    except Exception:
        return jsonify({"error": "Quantity must be a number"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO food_donation
        (food_type, quantity, original_quantity, accepted_quantity, donation_status,
         time, date_of_donation, donor_id)
        VALUES (?, ?, ?, 0, 'Pending', ?, ?, ?)
    """, (d.get('food_type'), quantity, quantity,
          d.get('time'), d.get('date_of_donation'), session['user_id']))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"success": True, "message": "Donation submitted successfully!", "donation_id": new_id}), 201

@app.route('/api/donations/<int:donation_id>', methods=['DELETE'])
def delete_donation(donation_id):
    if 'user_id' not in session or session.get('role') != 'donor':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM food_donation WHERE donation_id=? AND donor_id=? AND donation_status='Pending'",
                (donation_id, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Donation cancelled"})

# ═════════════════════════════════════════════════════════════
# API — NGO ENDPOINTS
# ═════════════════════════════════════════════════════════════

@app.route('/api/ngo/profile')
def ngo_profile():
    if 'user_id' not in session or session.get('role') != 'ngo':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT ngo_name, contact_no, address, capacity, priority_level FROM ngo WHERE ngo_id=?", (session['user_id'],))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "ngo_name": row['ngo_name'],
        "contact_no": row['contact_no'],
        "address": row['address'],
        "capacity": row['capacity'],
        "priority_level": row['priority_level']
    })

@app.route('/api/ngo/update', methods=['POST'])
def update_ngo_profile():
    if 'user_id' not in session or session.get('role') != 'ngo':
        return jsonify({"error": "Unauthorized"}), 401
    d = request.get_json()
    capacity_raw = d.get('capacity', '')
    try:
        capacity = int(capacity_raw) if str(capacity_raw).strip() != '' else 0
    except (ValueError, TypeError):
        capacity = 0

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE ngo SET ngo_name=?, contact_no=?, address=?, capacity=?, priority_level=? WHERE ngo_id=?",
        (d.get('ngo_name'), d.get('contact_no'), d.get('address'), capacity, d.get('priority_level'), session['user_id'])
    )
    conn.commit()
    conn.close()
    session['user_name'] = d.get('ngo_name')
    return jsonify({"success": True, "message": "Profile updated"})

@app.route('/api/ngo/stats')
def ngo_stats():
    if 'user_id' not in session or session.get('role') != 'ngo':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    run_expiry(conn)
    cur = conn.cursor()
    nid = session['user_id']
    cur.execute("SELECT COUNT(*) FROM delivery WHERE ngo_id=?", (nid,))
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM delivery WHERE ngo_id=? AND delivery_status='Pending'", (nid,))
    pending = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM delivery WHERE ngo_id=? AND delivery_status='Delivered'", (nid,))
    delivered = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM food_donation WHERE donation_status='Pending'")
    available = cur.fetchone()[0]
    conn.close()
    return jsonify({"success": True, "stats": {
        "total": total, "pending": pending, "delivered": delivered, "available": available
    }})

@app.route('/api/ngo/available-donations')
def ngo_available_donations():
    if 'user_id' not in session or session.get('role') != 'ngo':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    run_expiry(conn)
    cur = conn.cursor()
    cur.execute("""
        SELECT fd.donation_id, fd.food_type, fd.quantity,
               fd.original_quantity, fd.accepted_quantity,
               fd.date_of_donation, fd.time,
               d.donor_name, d.contact_no AS donor_contact, d.address AS donor_address,
               d.hygiene_rating AS donor_rating
        FROM food_donation fd
        LEFT JOIN donor d ON d.donor_id = fd.donor_id
        WHERE fd.donation_status = 'Pending'
        ORDER BY fd.donation_id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    data = []
    for r in rows:
        data.append({
            "donation_id": r['donation_id'], "food_type": r['food_type'], "quantity": r['quantity'],
            "original_quantity": r['original_quantity'], "accepted_quantity": r['accepted_quantity'],
            "date_of_donation": str(r['date_of_donation']) if r['date_of_donation'] else None,
            "time": str(r['time']) if r['time'] else None,
            "donor_name": r['donor_name'], "donor_contact": r['donor_contact'], "donor_address": r['donor_address'],
            "donor_rating": float(r['donor_rating'] or 0.0)
        })
    return jsonify({"success": True, "data": data})

@app.route('/api/ngo/accept-donation', methods=['POST'])
def ngo_accept_donation():
    if 'user_id' not in session or session.get('role') != 'ngo':
        return jsonify({"error": "Unauthorized"}), 401

    d = request.get_json()
    donation_id = d.get('donation_id')
    ngo_id = session['user_id']
    raw_qty = d.get('accepted_qty')

    try:
        accepted_qty = int(raw_qty) if raw_qty is not None and str(raw_qty).strip() != '' else None
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid accepted_qty"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT donation_id, quantity, original_quantity, accepted_quantity,
               food_type, time, date_of_donation, donor_id
        FROM food_donation
        WHERE donation_id = ? AND donation_status = 'Pending'
    """, (donation_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Donation no longer available"}), 400

    avail_qty = row['quantity']
    orig_qty = row['original_quantity'] or avail_qty
    food_type = row['food_type']
    fdtime = row['time']
    fddate = row['date_of_donation']
    donor_id = row['donor_id']

    if accepted_qty is None:
        accepted_qty = avail_qty

    if accepted_qty <= 0 or accepted_qty > avail_qty:
        conn.close()
        return jsonify({"error": f"Invalid quantity. Available: {avail_qty}"}), 400

    is_partial = (accepted_qty < avail_qty)
    remaining = avail_qty - accepted_qty

    if is_partial:
        # Update existing record remaining quantity
        cur.execute("""
            UPDATE food_donation
            SET quantity = ?,
                accepted_quantity = COALESCE(accepted_quantity, 0) + ?,
                original_quantity = ?
            WHERE donation_id = ?
        """, (remaining, accepted_qty, orig_qty, donation_id))

        # Insert new accepted child record
        cur.execute("""
            INSERT INTO food_donation
            (food_type, quantity, original_quantity, accepted_quantity, donation_status,
             time, date_of_donation, donor_id, parent_donation_id)
            VALUES (?, ?, ?, ?, 'Accepted', ?, ?, ?, ?)
        """, (food_type, accepted_qty, accepted_qty, accepted_qty,
              fdtime, fddate, donor_id, donation_id))
        working_donation_id = cur.lastrowid
    else:
        cur.execute("""
            UPDATE food_donation
            SET donation_status = 'Accepted',
                accepted_quantity = ?,
                original_quantity = ?
            WHERE donation_id = ?
        """, (accepted_qty, orig_qty, donation_id))
        working_donation_id = donation_id

    # Create Pickup record
    cur.execute("""
        INSERT INTO pickup (time, status, otp_code, donation_id, volunteer_id)
        VALUES (DATETIME('now'), 'Pending', NULL, ?, NULL)
    """, (working_donation_id,))
    pickup_id = cur.lastrowid

    # Create Delivery record
    cur.execute("""
        INSERT INTO delivery (time, receiver_name, delivery_status, pickup_id, ngo_id)
        VALUES (DATETIME('now'), ?, 'Pending', ?, ?)
    """, (session['user_name'], pickup_id, ngo_id))

    conn.commit()
    conn.close()

    msg = (
        f"Partial acceptance: {accepted_qty} meals accepted, {remaining} meals still available for other NGOs."
        if is_partial else
        "Donation accepted! Pickup task created for volunteers."
    )
    return jsonify({
        "success": True,
        "message": msg,
        "pickup_id": pickup_id,
        "is_partial": is_partial,
        "accepted_qty": accepted_qty,
        "remaining_qty": remaining if is_partial else 0
    })

@app.route('/api/ngo/orders')
def ngo_orders():
    if 'user_id' not in session or session.get('role') != 'ngo':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT dl.delivery_id, dl.delivery_status, dl.time,
               fd.food_type,  fd.quantity,
               fd.original_quantity, fd.parent_donation_id,
               d.donor_name,  d.address   AS donor_address,
               v.name         AS volunteer_name,
               v.contact_no   AS volunteer_contact,
               v.vehicle_type,
               p.status       AS pickup_status,
               p.otp_code,
               p.pickup_id,
               fd.donation_id,
               d.hygiene_rating AS donor_rating
        FROM delivery dl
        JOIN pickup        p  ON p.pickup_id   = dl.pickup_id
        JOIN food_donation fd ON fd.donation_id = p.donation_id
        JOIN donor         d  ON d.donor_id     = fd.donor_id
        LEFT JOIN volunteer v ON v.volunteer_id = p.volunteer_id
        WHERE dl.ngo_id = ?
        ORDER BY dl.delivery_id DESC
    """, (session['user_id'],))
    rows = cur.fetchall()
    conn.close()
    data = []
    for r in rows:
        data.append({
            "delivery_id": r['delivery_id'], "delivery_status": r['delivery_status'],
            "time": str(r['time']) if r['time'] else None,
            "food_type": r['food_type'], "quantity": r['quantity'],
            "original_quantity": r['original_quantity'], "parent_donation_id": r['parent_donation_id'],
            "donor_name": r['donor_name'], "donor_address": r['donor_address'],
            "volunteer_name": r['volunteer_name'], "volunteer_contact": r['volunteer_contact'],
            "vehicle_type": r['vehicle_type'], "pickup_status": r['pickup_status'],
            "otp_code": r['otp_code'], "pickup_id": r['pickup_id'], "donation_id": r['donation_id'],
            "donor_rating": float(r['donor_rating'] or 0.0)
        })
    return jsonify({"success": True, "data": data})

@app.route('/api/ngo/mark-received', methods=['POST'])
def ngo_mark_received():
    if 'user_id' not in session or session.get('role') != 'ngo':
        return jsonify({"error": "Unauthorized"}), 401
    d = request.get_json()
    delivery_id = d.get('delivery_id')
    pickup_id = d.get('pickup_id')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE delivery SET delivery_status='Delivered' WHERE delivery_id=? AND ngo_id=?", (delivery_id, session['user_id']))
    cur.execute("UPDATE pickup SET status='Delivered' WHERE pickup_id=?", (pickup_id,))
    cur.execute("""
        UPDATE volunteer SET availability_status='Available'
        WHERE volunteer_id=(SELECT volunteer_id FROM pickup WHERE pickup_id=?)
    """, (pickup_id,))
    cur.execute("""
        UPDATE food_donation SET donation_status='Completed'
        WHERE donation_id=(SELECT donation_id FROM pickup WHERE pickup_id=?)
    """, (pickup_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Marked as received!"})

@app.route('/api/ngo/feedback', methods=['POST'])
def submit_ngo_feedback():
    if 'user_id' not in session or session.get('role') != 'ngo':
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    donation_id = data.get('donation_id')
    rating = data.get('rating', 5)
    comments = data.get('comments', "")
    hygiene = data.get('hygiene_score', 5)

    if not donation_id:
        return jsonify({"success": False, "error": "Donation ID missing"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT donor_id FROM food_donation WHERE donation_id = ?", (donation_id,))
    donor = cur.fetchone()
    if not donor:
        conn.close()
        return jsonify({"error": "Donation not found"}), 404
    donor_id = donor['donor_id']

    today_str = date.today().strftime('%Y-%m-%d')
    cur.execute("""
        INSERT INTO feedback
        (donation_id, donor_id, ngo_id, rating, comments, hygiene_score, feedback_date, from_ngo)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    """, (donation_id, donor_id, session['user_id'], rating, comments, hygiene, today_str))

    # Recalculate Donor Hygiene Rating
    cur.execute("""
        SELECT AVG(hygiene_score) FROM feedback WHERE donor_id = ? AND from_ngo = 1
    """, (donor_id,))
    avg_score = cur.fetchone()[0] or 5.0

    cur.execute("UPDATE donor SET hygiene_rating = ? WHERE donor_id = ?", (round(float(avg_score), 1), donor_id))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Feedback & rating submitted successfully!"})

@app.route('/api/ngo/feedback-given', methods=['GET'])
def ngo_feedback_given():
    if 'user_id' not in session or session.get('role') != 'ngo':
        return jsonify({"error": "Unauthorized"}), 401

    ngo_id = session['user_id']
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT f.rating, f.comments, f.hygiene_score, f.feedback_date,
               d.food_type, dnr.donor_name
        FROM feedback f
        JOIN food_donation d ON f.donation_id = d.donation_id
        JOIN donor dnr ON f.donor_id = dnr.donor_id
        WHERE f.ngo_id = ? AND f.from_ngo = 1
        ORDER BY f.feedback_id DESC
    """, (ngo_id,))
    rows = cur.fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append({
            "rating": row['rating'], "comments": row['comments'], "hygiene_score": row['hygiene_score'],
            "feedback_date": str(row['feedback_date']), "food_type": row['food_type'], "donor_name": row['donor_name']
        })
    return jsonify({"success": True, "data": result})

@app.route('/api/ngo/wasted-donations')
def ngo_wasted_donations():
    if 'user_id' not in session or session.get('role') != 'ngo':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    run_expiry(conn)
    cur = conn.cursor()
    cur.execute("""
        SELECT fd.donation_id, fd.food_type, fd.quantity,
               fd.time, fd.date_of_donation,
               fd.original_quantity, fd.accepted_quantity
        FROM food_donation fd
        WHERE fd.donation_status = 'Wasted'
        ORDER BY fd.donation_id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    data = []
    for r in rows:
        data.append({
            "donation_id": r['donation_id'], "food_type": r['food_type'],
            "quantity": r['quantity'], "available_until": str(r['time']) if r['time'] else None,
            "date_of_donation": str(r['date_of_donation']) if r['date_of_donation'] else None,
            "original_quantity": r['original_quantity'], "accepted_quantity": r['accepted_quantity']
        })
    return jsonify({"success": True, "data": data})

# ═════════════════════════════════════════════════════════════
# API — VOLUNTEER ENDPOINTS
# ═════════════════════════════════════════════════════════════

@app.route('/api/volunteer/profile')
def volunteer_profile():
    if 'user_id' not in session or session.get('role') != 'volunteer':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, contact_no, vehicle_type, availability_status FROM volunteer WHERE volunteer_id=?", (session['user_id'],))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "name": row['name'],
        "contact_no": row['contact_no'],
        "vehicle_type": row['vehicle_type'],
        "availability_status": row['availability_status']
    })

@app.route('/api/volunteer/update', methods=['POST'])
def update_volunteer_profile():
    if 'user_id' not in session or session.get('role') != 'volunteer':
        return jsonify({"error": "Unauthorized"}), 401
    d = request.get_json()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE volunteer SET name=?, contact_no=?, vehicle_type=?, availability_status=? WHERE volunteer_id=?",
        (d.get('name'), d.get('contact_no'), d.get('vehicle_type'), d.get('availability_status'), session['user_id'])
    )
    conn.commit()
    conn.close()
    session['user_name'] = d.get('name')
    return jsonify({"success": True, "message": "Profile updated"})

@app.route('/api/volunteer/stats')
def volunteer_stats():
    if 'user_id' not in session or session.get('role') != 'volunteer':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    vid = session['user_id']
    cur.execute("SELECT COUNT(*) FROM pickup WHERE volunteer_id=?", (vid,))
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM pickup WHERE volunteer_id=? AND status='Pending'", (vid,))
    pending = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM pickup WHERE volunteer_id=? AND status='In Progress'", (vid,))
    in_progress = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM pickup WHERE volunteer_id=? AND status='Delivered'", (vid,))
    delivered = cur.fetchone()[0]
    conn.close()
    return jsonify({"success": True, "stats": {
        "total": total, "pending": pending, "in_progress": in_progress, "delivered": delivered
    }})

@app.route('/api/volunteer/pickups')
def volunteer_own_pickups():
    if 'user_id' not in session or session.get('role') != 'volunteer':
        return jsonify({"error": "Unauthorized"}), 401

    vid = session['user_id']
    conn = get_db()
    cur = conn.cursor()

    # Open Pickups (Unassigned)
    cur.execute("""
        SELECT p.pickup_id,   p.time,         p.status,      p.otp_code,
               fd.food_type,  fd.quantity,
               d.donor_name,  d.contact_no    AS donor_contact,
               d.address      AS donor_address,
               n.ngo_name,    n.address       AS ngo_address,
               n.contact_no   AS ngo_contact,
               dl.delivery_id, dl.delivery_status,
               d.hygiene_rating AS donor_rating
        FROM pickup p
        JOIN food_donation fd ON fd.donation_id = p.donation_id
        JOIN donor         d  ON d.donor_id     = fd.donor_id
        LEFT JOIN delivery dl ON dl.pickup_id   = p.pickup_id
        LEFT JOIN ngo      n  ON n.ngo_id       = dl.ngo_id
        WHERE p.volunteer_id IS NULL AND p.status = 'Pending'
        ORDER BY p.pickup_id DESC
    """)
    open_rows = cur.fetchall()

    # My Claimed Pickups
    cur.execute("""
        SELECT p.pickup_id,   p.time,         p.status,      p.otp_code,
               fd.food_type,  fd.quantity,
               d.donor_name,  d.contact_no    AS donor_contact,
               d.address      AS donor_address,
               n.ngo_name,    n.address       AS ngo_address,
               n.contact_no   AS ngo_contact,
               dl.delivery_id, dl.delivery_status,
               d.hygiene_rating AS donor_rating
        FROM pickup p
        JOIN food_donation fd ON fd.donation_id = p.donation_id
        JOIN donor         d  ON d.donor_id     = fd.donor_id
        LEFT JOIN delivery dl ON dl.pickup_id   = p.pickup_id
        LEFT JOIN ngo      n  ON n.ngo_id       = dl.ngo_id
        WHERE p.volunteer_id = ?
        ORDER BY p.pickup_id DESC
    """, (vid,))
    my_rows = cur.fetchall()
    conn.close()

    def row_to_dict(r, is_mine):
        return {
            "pickup_id": r['pickup_id'], "time": str(r['time']) if r['time'] else None,
            "status": r['status'], "otp_code": r['otp_code'],
            "food_type": r['food_type'], "quantity": r['quantity'],
            "donor_name": r['donor_name'], "donor_contact": r['donor_contact'], "donor_address": r['donor_address'],
            "ngo_name": r['ngo_name'], "ngo_address": r['ngo_address'], "ngo_contact": r['ngo_contact'],
            "delivery_id": r['delivery_id'], "delivery_status": r['delivery_status'],
            "donor_rating": float(r['donor_rating'] or 0.0),
            "is_mine": is_mine
        }

    all_mine = [row_to_dict(r, True) for r in my_rows]
    available = [row_to_dict(r, False) for r in open_rows]

    return jsonify({
        "success": True,
        "data": all_mine,
        "available": available
    })

@app.route('/api/volunteer/accept-assignment', methods=['POST'])
def volunteer_accept_assignment():
    if 'user_id' not in session or session.get('role') != 'volunteer':
        return jsonify({"error": "Unauthorized"}), 401

    d = request.get_json()
    pickup_id = d.get('pickup_id')
    vid = session['user_id']

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT volunteer_id, status FROM pickup WHERE pickup_id = ?", (pickup_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Pickup not found"}), 404

    if row['volunteer_id'] is not None:
        conn.close()
        return jsonify({"success": False, "error": "This pickup task was just claimed by another volunteer."}), 409

    if row['status'] != 'Pending':
        conn.close()
        return jsonify({"success": False, "error": "This pickup is no longer pending."}), 409

    otp = str(random.randint(1000, 9999))

    cur.execute("UPDATE pickup SET volunteer_id = ?, otp_code = ? WHERE pickup_id = ?", (vid, otp, pickup_id))
    cur.execute("UPDATE volunteer SET availability_status = 'Busy' WHERE volunteer_id = ?", (vid,))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Pickup task claimed! OTP: {otp}. Proceed to pickup location.",
        "otp": otp,
        "pickup_id": pickup_id
    })

@app.route('/api/volunteer/update-pickup', methods=['POST'])
def volunteer_update_pickup():
    if 'user_id' not in session or session.get('role') != 'volunteer':
        return jsonify({"error": "Unauthorized"}), 401

    d = request.get_json()
    pickup_id = d.get('pickup_id')
    status = d.get('status')
    otp_input = d.get('otp')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT volunteer_id, otp_code FROM pickup WHERE pickup_id=?", (pickup_id,))
    row = cur.fetchone()

    if not row or row['volunteer_id'] != session['user_id']:
        conn.close()
        return jsonify({"error": "Not authorized for this pickup."}), 403

    if status == 'Delivered':
        stored_otp = str(row['otp_code']).strip() if row['otp_code'] is not None else ''
        provided = str(otp_input).strip() if otp_input is not None else ''
        if not provided or provided != stored_otp:
            conn.close()
            return jsonify({"error": "Invalid OTP code. Delivery cannot be verified."}), 400

    cur.execute("UPDATE pickup SET status=? WHERE pickup_id=?", (status, pickup_id))

    if status == 'Delivered':
        cur.execute("UPDATE delivery SET delivery_status='Delivered' WHERE pickup_id=?", (pickup_id,))
        cur.execute("UPDATE volunteer SET availability_status='Available' WHERE volunteer_id=?", (session['user_id'],))
        cur.execute("""
            UPDATE food_donation SET donation_status='Completed'
            WHERE donation_id = (SELECT donation_id FROM pickup WHERE pickup_id=?)
        """, (pickup_id,))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Pickup status updated to {status}"})

@app.route('/api/volunteer/wasted-donations')
def volunteer_wasted_donations():
    if 'user_id' not in session or session.get('role') != 'volunteer':
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    run_expiry(conn)
    cur = conn.cursor()
    cur.execute("""
        SELECT fd.donation_id, fd.food_type, fd.quantity,
               fd.time, fd.date_of_donation,
               fd.original_quantity, fd.accepted_quantity
        FROM food_donation fd
        WHERE fd.donation_status = 'Wasted'
        ORDER BY fd.donation_id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    data = []
    for r in rows:
        data.append({
            "donation_id": r['donation_id'], "food_type": r['food_type'],
            "quantity": r['quantity'], "available_until": str(r['time']) if r['time'] else None,
            "date_of_donation": str(r['date_of_donation']) if r['date_of_donation'] else None,
            "original_quantity": r['original_quantity'], "accepted_quantity": r['accepted_quantity']
        })
    return jsonify({"success": True, "data": data})

# ═════════════════════════════════════════════════════════════
# API — DASHBOARD & HEALTH
# ═════════════════════════════════════════════════════════════

@app.route('/api/dashboard')
def dashboard():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM donor")
    total_donors = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ngo")
    total_ngos = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM volunteer WHERE availability_status='Available'")
    available_volunteers = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM food_donation")
    total_donations = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM food_donation WHERE donation_status='Pending'")
    pending_donations = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM food_donation WHERE donation_status='Completed'")
    completed_donations = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM pickup WHERE status='In Progress'")
    active_pickups = cur.fetchone()[0]
    cur.execute("SELECT ROUND(AVG(rating), 1) FROM feedback")
    avg_rating = cur.fetchone()[0] or 5.0
    conn.close()

    return jsonify({
        "success": True,
        "stats": {
            "total_donors": total_donors,
            "total_ngos": total_ngos,
            "available_volunteers": available_volunteers,
            "total_donations": total_donations,
            "pending_donations": pending_donations,
            "completed_donations": completed_donations,
            "active_pickups": active_pickups,
            "avg_rating": float(avg_rating or 5.0)
        }
    })

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "service": "Mobile FoodBridge App Backend"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 60)
    print(f"  Mobile FoodBridge App Backend Running on port {port}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=False)
