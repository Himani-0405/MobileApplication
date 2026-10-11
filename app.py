import os
import sys
import random
import hashlib
import uuid
from datetime import datetime, date
from flask import (Flask, render_template, jsonify, request,
                   redirect, url_for, session, send_file, abort)
from flask_cors import CORS
from database import get_db, init_db, expire_donations_db
from rewards_service import (
    process_donation_completed, process_delivery_completed,
    get_donor_impact_summary, get_volunteer_impact_summary,
    get_ngo_impact_summary, confirm_ngo_distribution,
    get_leaderboard, get_user_rewards_history, get_user_certificates,
    get_user_redemptions, redeem_reward, admin_revoke_activity_points,
    REWARD_CATALOG_ITEMS, CERTIFICATES_DIR, _build_pdf_certificate,
    get_or_create_account
)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'foodbridge_mobile_secret_key_2026')
CORS(app, supports_credentials=True)

# ─── Private document storage (outside static/) ───────────────────────────────
PRIVATE_UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'private_uploads')
os.makedirs(os.path.join(PRIVATE_UPLOADS_DIR, 'donor_docs'), exist_ok=True)
os.makedirs(os.path.join(PRIVATE_UPLOADS_DIR, 'ngo_docs'), exist_ok=True)
os.makedirs(os.path.join(PRIVATE_UPLOADS_DIR, 'volunteer_docs'), exist_ok=True)
os.makedirs(os.path.join(PRIVATE_UPLOADS_DIR, 'food_photos'), exist_ok=True)

ALLOWED_DOC_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
ALLOWED_PHOTO_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Initialize Database Schema & Seed Data
init_db()


def run_expiry(conn):
    try:
        expire_donations_db(conn)
    except Exception as e:
        print("Expiry error:", e)


def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _allowed_file(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def _safe_filename(original: str) -> str:
    """Generate a UUID-based filename preserving extension."""
    ext = original.rsplit('.', 1)[-1].lower() if '.' in original else 'bin'
    return f"{uuid.uuid4().hex}.{ext}"


def _save_private_file(file_obj, subfolder: str, allowed_extensions) -> str | None:
    """Save an uploaded file to private storage. Returns relative path or None."""
    if not file_obj or file_obj.filename == '':
        return None
    if not _allowed_file(file_obj.filename, allowed_extensions):
        return None
    file_obj.seek(0, 2)
    size = file_obj.tell()
    file_obj.seek(0)
    if size > MAX_FILE_SIZE_BYTES:
        return None
    safe_name = _safe_filename(file_obj.filename)
    dest_dir = os.path.join(PRIVATE_UPLOADS_DIR, subfolder)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, safe_name)
    file_obj.save(dest_path)
    return os.path.join(subfolder, safe_name)


def _is_admin():
    return session.get('role') == 'admin'


def _is_donor():
    return 'user_id' in session and session.get('role') == 'donor'


def _is_ngo():
    return 'user_id' in session and session.get('role') == 'ngo'


def _is_volunteer():
    return 'user_id' in session and session.get('role') == 'volunteer'


# ═════════════════════════════════════════════════════════════
# PAGE ROUTE
# ═════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/admin')
def admin_page():
    return render_template('admin.html')


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
        cur.execute(
            "SELECT donor_id, donor_name, password FROM donor WHERE LOWER(TRIM(donor_name)) = LOWER(TRIM(?))",
            (name,))
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
        # Support both name-only (legacy) and name+password
        cur.execute(
            "SELECT ngo_id, ngo_name, password FROM ngo WHERE LOWER(TRIM(ngo_name)) = LOWER(TRIM(?))",
            (name,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return jsonify({"success": False, "error": "NGO not found."}), 404
        # If NGO has a password stored, verify it
        if row['password'] and str(row['password']).strip() != password:
            return jsonify({"success": False, "error": "Incorrect password."}), 401
        session.clear()
        session['user_id'] = row['ngo_id']
        session['user_name'] = row['ngo_name']
        session['role'] = 'ngo'
        return jsonify({"success": True, "role": "ngo", "user_name": row['ngo_name']})

    elif role == 'volunteer':
        cur.execute(
            "SELECT volunteer_id, name, password FROM volunteer WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))",
            (name,))
        vol = cur.fetchone()
        conn.close()
        if not vol:
            return jsonify({"success": False, "error": "Volunteer not found."}), 404
        # If volunteer has a password stored, verify it
        if vol['password'] and str(vol['password']).strip() != password:
            return jsonify({"success": False, "error": "Incorrect password."}), 401
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
    donor_type = data.get('donor_type', 'Individual').strip()

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
            (name, donor_type, mobile, '', 5.0, password, 'donor', email)
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
            "INSERT INTO volunteer (name, contact_no, vehicle_type, availability_status, password, email) VALUES (?, ?, ?, ?, ?, ?)",
            (name, mobile, 'Bike', 'Available', password, email)
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
            "INSERT INTO ngo (ngo_name, contact_no, address, capacity, priority_level, password, email) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, mobile, address, capacity, priority, password, email)
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
# ADMIN AUTH ROUTES
# ═════════════════════════════════════════════════════════════

@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json() if request.is_json else request.form
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT admin_id, username, password_hash FROM admin_user WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"success": False, "error": "Invalid credentials"}), 401

    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if pw_hash != row['password_hash']:
        return jsonify({"success": False, "error": "Invalid credentials"}), 401

    session.clear()
    session['admin_id'] = row['admin_id']
    session['user_name'] = row['username']
    session['role'] = 'admin'
    return jsonify({"success": True, "username": row['username']})


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return jsonify({"success": True})


@app.route('/api/admin/me')
def admin_me():
    if not _is_admin():
        return jsonify({"authenticated": False}), 200
    return jsonify({"authenticated": True, "username": session.get('user_name')})


# ═════════════════════════════════════════════════════════════
# ADMIN — VERIFICATION DASHBOARD
# ═════════════════════════════════════════════════════════════

@app.route('/api/admin/pending-donors')
def admin_pending_donors():
    if not _is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT dv.id, dv.donor_id, dv.fssai_number, dv.verification_status,
               dv.rejection_reason, dv.submitted_at,
               d.donor_name, d.donor_type, d.email, d.contact_no
        FROM donor_verification dv
        JOIN donor d ON d.donor_id = dv.donor_id
        ORDER BY dv.submitted_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    res_list = []
    for r in rows:
        d = dict(r)
        d['verification_id'] = r['id']
        res_list.append(d)
    return jsonify({"success": True, "data": res_list, "donors": res_list})


@app.route('/api/admin/pending-ngos')
def admin_pending_ngos():
    if not _is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT nv.id, nv.ngo_id, nv.darpan_id, nv.reg_type, nv.reg_12a,
               nv.reg_80g, nv.contact_person, nv.contact_phone,
               nv.verification_status, nv.rejection_reason, nv.submitted_at,
               n.ngo_name, n.contact_no, n.email
        FROM ngo_verification nv
        JOIN ngo n ON n.ngo_id = nv.ngo_id
        ORDER BY nv.submitted_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    res_list = []
    for r in rows:
        d = dict(r)
        d['verification_id'] = r['id']
        res_list.append(d)
    return jsonify({"success": True, "data": res_list, "ngos": res_list})


@app.route('/api/admin/pending-volunteers')
def admin_pending_volunteers():
    if not _is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT vv.id, vv.volunteer_id, vv.vehicle_reg_no,
               vv.emergency_contact_name, vv.emergency_contact_phone,
               vv.verification_status, vv.rejection_reason, vv.submitted_at,
               v.name, v.contact_no, v.email, v.vehicle_type
        FROM volunteer_verification vv
        JOIN volunteer v ON v.volunteer_id = vv.volunteer_id
        ORDER BY vv.submitted_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    res_list = []
    for r in rows:
        d = dict(r)
        d['verification_id'] = r['id']
        res_list.append(d)
    return jsonify({"success": True, "data": res_list, "volunteers": res_list})


@app.route('/api/admin/approve', methods=['POST'])
def admin_approve():
    if not _is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    entity_type = data.get('type')   # 'donor' | 'ngo' | 'volunteer'
    entity_id   = data.get('id') or data.get('verification_id')     # the verification table row id

    if entity_type not in ('donor', 'ngo', 'volunteer') or not entity_id:
        return jsonify({"error": "Invalid parameters"}), 400

    table_map = {
        'donor': 'donor_verification',
        'ngo': 'ngo_verification',
        'volunteer': 'volunteer_verification'
    }
    table = table_map[entity_type]
    now = datetime.now().isoformat()

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE {table} SET verification_status='Verified', rejection_reason=NULL, reviewed_at=? WHERE id=?",
        (now, entity_id)
    )
    if cur.rowcount == 0:
        conn.close()
        return jsonify({"error": "Record not found"}), 404
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"{entity_type.title()} approved."})


@app.route('/api/admin/reject', methods=['POST'])
def admin_reject():
    if not _is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    entity_type = data.get('type')
    entity_id   = data.get('id') or data.get('verification_id')
    reason      = (data.get('reason') or data.get('rejection_reason') or '').strip()

    if entity_type not in ('donor', 'ngo', 'volunteer') or not entity_id:
        return jsonify({"error": "Invalid parameters"}), 400
    if not reason:
        return jsonify({"error": "Rejection reason is required"}), 400

    table_map = {
        'donor': 'donor_verification',
        'ngo': 'ngo_verification',
        'volunteer': 'volunteer_verification'
    }
    table = table_map[entity_type]
    now = datetime.now().isoformat()

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE {table} SET verification_status='Rejected', rejection_reason=?, reviewed_at=? WHERE id=?",
        (reason, now, entity_id)
    )
    if cur.rowcount == 0:
        conn.close()
        return jsonify({"error": "Record not found"}), 404
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"{entity_type.title()} rejected."})


# Private document serving — admin only
@app.route('/admin/doc/<path:rel_path>')
def serve_private_doc(rel_path):
    if not _is_admin():
        abort(403)
    # Prevent path traversal
    safe_path = os.path.normpath(rel_path)
    if '..' in safe_path or safe_path.startswith('/'):
        abort(400)
    full_path = os.path.join(PRIVATE_UPLOADS_DIR, safe_path)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path)


# ═════════════════════════════════════════════════════════════
# API — DONOR ENDPOINTS
# ═════════════════════════════════════════════════════════════

@app.route('/api/donor/profile')
def donor_profile():
    if not _is_donor():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.donor_name, d.contact_no, d.address, d.hygiene_rating,
               d.email, d.donor_type,
               dv.fssai_number, dv.verification_status AS fssai_status
        FROM donor d
        LEFT JOIN donor_verification dv ON dv.donor_id = d.donor_id
        WHERE d.donor_id=?
    """, (session['user_id'],))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "donor_name": row['donor_name'],
        "contact_no": row['contact_no'],
        "address": row['address'],
        "hygiene_rating": float(row['hygiene_rating'] or 0.0),
        "email": row['email'],
        "donor_type": row['donor_type'],
        "fssai_number": row['fssai_number'],
        "fssai_status": row['fssai_status'] or 'Not Submitted'
    })


@app.route('/api/donor/update', methods=['POST'])
def update_donor_profile():
    if not _is_donor():
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


@app.route('/api/donor/submit-verification', methods=['POST'])
def donor_submit_verification():
    if not _is_donor():
        return jsonify({"error": "Unauthorized"}), 401

    donor_id = session['user_id']
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT donor_type FROM donor WHERE donor_id=?", (donor_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Donor not found"}), 404

    is_business = row['donor_type'] not in ('Individual',)
    fssai_number = (request.form.get('fssai_number') or request.form.get('fssai_no') or '').strip()
    fssai_cert = request.files.get('fssai_cert')

    # Validate FSSAI number: must be exactly 14 digits
    if fssai_number:
        if not fssai_number.isdigit() or len(fssai_number) != 14:
            return jsonify({"error": "FSSAI number must be exactly 14 digits"}), 400

    # Business donors must provide FSSAI number + certificate
    if is_business:
        if not fssai_number:
            return jsonify({"error": "Business donors must provide FSSAI license number (14 digits)"}), 400
        if not fssai_cert or fssai_cert.filename == '':
            return jsonify({"error": "Business donors must upload FSSAI certificate"}), 400

    cert_path = None
    if fssai_cert and fssai_cert.filename != '':
        cert_path = _save_private_file(fssai_cert, 'donor_docs', ALLOWED_DOC_EXTENSIONS)
        if cert_path is None:
            return jsonify({"error": "Invalid file. Allowed: PDF, JPG, PNG. Max 5MB."}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM donor_verification WHERE donor_id=?", (donor_id,))
    existing = cur.fetchone()
    now = datetime.now().isoformat()

    if existing:
        cur.execute("""
            UPDATE donor_verification
            SET fssai_number=?, fssai_cert_path=COALESCE(?, fssai_cert_path),
                verification_status='Pending', rejection_reason=NULL, submitted_at=?
            WHERE donor_id=?
        """, (fssai_number or None, cert_path, now, donor_id))
    else:
        cur.execute("""
            INSERT INTO donor_verification (donor_id, fssai_number, fssai_cert_path, verification_status, submitted_at)
            VALUES (?, ?, ?, 'Pending', ?)
        """, (donor_id, fssai_number or None, cert_path, now))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Verification submitted. Awaiting admin review."})


@app.route('/api/donor/verification-status')
def donor_verification_status():
    if not _is_donor():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT dv.verification_status, dv.rejection_reason, dv.fssai_number, dv.submitted_at
        FROM donor_verification dv
        WHERE dv.donor_id=?
    """, (session['user_id'],))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({
            "success": True,
            "donor_id": session['user_id'],
            "verification": {"verification_status": "None", "fssai_no": None},
            "status": "Not Submitted"
        })
    return jsonify({
        "success": True,
        "donor_id": session['user_id'],
        "verification": {
            "verification_status": row['verification_status'],
            "rejection_reason": row['rejection_reason'],
            "fssai_no": row['fssai_number'],
            "submitted_at": str(row['submitted_at'])
        },
        "status": row['verification_status'],
        "rejection_reason": row['rejection_reason'],
        "fssai_number": row['fssai_number'],
        "submitted_at": str(row['submitted_at'])
    })


@app.route('/api/donor/stats')
def donor_stats():
    if not _is_donor():
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
    if not _is_donor():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    run_expiry(conn)
    cur = conn.cursor()
    cur.execute("""
        SELECT fd.donation_id, fd.food_type, fd.quantity, fd.donation_status,
               fd.time, fd.date_of_donation,
               fd.original_quantity, fd.accepted_quantity,
               fd.cooked_at, fd.food_category,
               fd.food_photo_path,
               p.status       AS pickup_status,
               p.otp_code,
               v.name         AS volunteer_name,
               v.contact_no   AS volunteer_contact,
               vv.verification_status AS vol_verified,
               vv.vehicle_reg_no,
               v.volunteer_id,
               dl.delivery_status,
               n.ngo_name
        FROM food_donation fd
        LEFT JOIN pickup    p  ON p.donation_id  = fd.donation_id
        LEFT JOIN volunteer v  ON v.volunteer_id = p.volunteer_id
        LEFT JOIN volunteer_verification vv ON vv.volunteer_id = v.volunteer_id
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
        photo_url = None
        if r['food_photo_path']:
            photo_url = f"/food-photo/{r['food_photo_path'].replace(os.sep, '/')}"
        data.append({
            "donation_id": r['donation_id'], "food_type": r['food_type'],
            "quantity": r['quantity'], "donation_status": r['donation_status'],
            "time": str(r['time']) if r['time'] else None,
            "date_of_donation": str(r['date_of_donation']) if r['date_of_donation'] else None,
            "original_quantity": r['original_quantity'],
            "accepted_quantity": r['accepted_quantity'],
            "cooked_at": r['cooked_at'],
            "food_category": r['food_category'],
            "food_photo": r['food_photo_path'],
            "food_photo_url": photo_url,
            "pickup_status": r['pickup_status'], "otp_code": r['otp_code'],
            "volunteer_name": r['volunteer_name'],
            "volunteer_contact": r['volunteer_contact'],
            "volunteer_verified": r['vol_verified'] == 'Verified' if r['vol_verified'] else False,
            "volunteer_vehicle_no": r['vehicle_reg_no'],
            "volunteer_id": r['volunteer_id'],
            "delivery_status": r['delivery_status'], "ngo_name": r['ngo_name']
        })
    return jsonify({"success": True, "data": data})


@app.route('/api/donor/wasted-donations')
def donor_wasted_donations():
    if not _is_donor():
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
    if not _is_donor():
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
            "hygiene_score": r['hygiene_score'],
            "feedback_date": str(r['feedback_date']) if r['feedback_date'] else None,
            "food_type": r['food_type'], "ngo_name": r['ngo_name']
        })
    return jsonify({"success": True, "data": data})


@app.route('/api/donations', methods=['POST'])
def create_donation():
    if not _is_donor():
        return jsonify({"error": "Unauthorized"}), 401

    # Handle both multipart (file upload) and JSON
    if request.content_type and 'multipart' in request.content_type:
        food_type = request.form.get('food_type', '').strip()
        quantity_raw = request.form.get('quantity', '')
        time_val = request.form.get('time', '')
        date_val = request.form.get('date_of_donation', '')
        cooked_at = request.form.get('cooked_at', '').strip() or None
        food_category = request.form.get('food_category', 'Vegetarian').strip()
        food_photo = request.files.get('food_photo')
    else:
        d = request.get_json() or {}
        food_type = d.get('food_type', '').strip()
        quantity_raw = d.get('quantity', '')
        time_val = d.get('time', '')
        date_val = d.get('date_of_donation', '')
        cooked_at = d.get('cooked_at') or None
        food_category = d.get('food_category', 'Vegetarian')
        food_photo = None

    if not food_type:
        return jsonify({"error": "Food type is required"}), 400
    if quantity_raw is None or str(quantity_raw).strip() == "":
        return jsonify({"error": "Quantity is required"}), 400
    try:
        quantity = int(quantity_raw)
    except Exception:
        return jsonify({"error": "Quantity must be a number"}), 400

    if food_category not in ('Vegetarian', 'Non-Vegetarian'):
        food_category = 'Vegetarian'

    # Save food photo to private uploads
    photo_path = None
    if food_photo and food_photo.filename != '':
        photo_path = _save_private_file(food_photo, 'food_photos', ALLOWED_PHOTO_EXTENSIONS)
        if photo_path is None:
            return jsonify({"error": "Invalid photo. Allowed: JPG, PNG, WEBP. Max 5MB."}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO food_donation
        (food_type, quantity, original_quantity, accepted_quantity, donation_status,
         time, date_of_donation, donor_id, cooked_at, food_category, food_photo_path)
        VALUES (?, ?, ?, 0, 'Pending', ?, ?, ?, ?, ?, ?)
    """, (food_type, quantity, quantity, time_val, date_val,
          session['user_id'], cooked_at, food_category, photo_path))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"success": True, "message": "Donation submitted successfully!", "donation_id": new_id}), 201


@app.route('/api/donations/<int:donation_id>', methods=['DELETE'])
def delete_donation(donation_id):
    if not _is_donor():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM food_donation WHERE donation_id=? AND donor_id=? AND donation_status='Pending'",
                (donation_id, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Donation cancelled"})


# Serve food photos — only to authenticated users (donor, ngo, volunteer, admin)
@app.route('/food-photo/<path:rel_path>')
def serve_food_photo(rel_path):
    if 'user_id' not in session and not _is_admin():
        abort(403)
    safe_path = os.path.normpath(rel_path)
    if '..' in safe_path or safe_path.startswith('/'):
        abort(400)
    # food photos are stored under food_photos/ inside PRIVATE_UPLOADS_DIR
    if not safe_path.startswith('food_photos'):
        safe_path = os.path.join('food_photos', safe_path)
    full_path = os.path.join(PRIVATE_UPLOADS_DIR, safe_path)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path)


# ═════════════════════════════════════════════════════════════
# API — NGO ENDPOINTS
# ═════════════════════════════════════════════════════════════

@app.route('/api/ngo/profile')
def ngo_profile():
    if not _is_ngo():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT n.ngo_name, n.contact_no, n.address, n.capacity, n.priority_level,
               nv.darpan_id, nv.reg_type, nv.reg_12a, nv.reg_80g,
               nv.contact_person, nv.contact_phone,
               nv.verification_status AS ngo_ver_status
        FROM ngo n
        LEFT JOIN ngo_verification nv ON nv.ngo_id = n.ngo_id
        WHERE n.ngo_id=?
    """, (session['user_id'],))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "ngo_name": row['ngo_name'],
        "contact_no": row['contact_no'],
        "address": row['address'],
        "capacity": row['capacity'],
        "priority_level": row['priority_level'],
        "darpan_id": row['darpan_id'],
        "reg_type": row['reg_type'],
        "reg_12a": row['reg_12a'],
        "reg_80g": row['reg_80g'],
        "contact_person": row['contact_person'],
        "contact_phone": row['contact_phone'],
        "ngo_ver_status": row['ngo_ver_status'] or 'Not Submitted'
    })


@app.route('/api/ngo/update', methods=['POST'])
def update_ngo_profile():
    if not _is_ngo():
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


@app.route('/api/ngo/submit-verification', methods=['POST'])
def ngo_submit_verification():
    if not _is_ngo():
        return jsonify({"error": "Unauthorized"}), 401

    ngo_id = session['user_id']
    darpan_id = request.form.get('darpan_id', '').strip()
    reg_type = request.form.get('reg_type', '').strip()
    reg_12a = request.form.get('reg_12a', '').strip() or None
    reg_80g = request.form.get('reg_80g', '').strip() or None
    contact_person = request.form.get('contact_person', '').strip()
    contact_phone = request.form.get('contact_phone', '').strip()
    reg_cert = request.files.get('reg_cert')

    if not darpan_id:
        return jsonify({"error": "NGO Darpan ID is required"}), 400
    if not contact_person or not contact_phone:
        return jsonify({"error": "Contact person name and phone are required"}), 400

    cert_path = None
    if reg_cert and reg_cert.filename != '':
        cert_path = _save_private_file(reg_cert, 'ngo_docs', ALLOWED_DOC_EXTENSIONS)
        if cert_path is None:
            return jsonify({"error": "Invalid file. Allowed: PDF, JPG, PNG. Max 5MB."}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM ngo_verification WHERE ngo_id=?", (ngo_id,))
    existing = cur.fetchone()
    now = datetime.now().isoformat()

    if existing:
        cur.execute("""
            UPDATE ngo_verification
            SET darpan_id=?, reg_cert_path=COALESCE(?, reg_cert_path),
                reg_type=?, reg_12a=?, reg_80g=?,
                contact_person=?, contact_phone=?,
                verification_status='Pending', rejection_reason=NULL, submitted_at=?
            WHERE ngo_id=?
        """, (darpan_id, cert_path, reg_type, reg_12a, reg_80g,
              contact_person, contact_phone, now, ngo_id))
    else:
        cur.execute("""
            INSERT INTO ngo_verification
            (ngo_id, darpan_id, reg_cert_path, reg_type, reg_12a, reg_80g,
             contact_person, contact_phone, verification_status, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?)
        """, (ngo_id, darpan_id, cert_path, reg_type, reg_12a, reg_80g,
              contact_person, contact_phone, now))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "NGO verification submitted. Awaiting admin review."})


@app.route('/api/ngo/verification-status')
def ngo_verification_status():
    if not _is_ngo():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT verification_status, rejection_reason, darpan_id, submitted_at,
               contact_person, contact_phone
        FROM ngo_verification WHERE ngo_id=?
    """, (session['user_id'],))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({
            "success": True,
            "ngo_id": session['user_id'],
            "verification": {"verification_status": "None", "darpan_id": None},
            "status": "Not Submitted"
        })
    return jsonify({
        "success": True,
        "ngo_id": session['user_id'],
        "verification": {
            "verification_status": row['verification_status'],
            "rejection_reason": row['rejection_reason'],
            "darpan_id": row['darpan_id'],
            "contact_person": row['contact_person'],
            "contact_phone": row['contact_phone'],
            "submitted_at": str(row['submitted_at'])
        },
        "status": row['verification_status'],
        "rejection_reason": row['rejection_reason'],
        "darpan_id": row['darpan_id'],
        "submitted_at": str(row['submitted_at'])
    })


@app.route('/api/ngo/stats')
def ngo_stats():
    if not _is_ngo():
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
    if not _is_ngo():
        return jsonify({"error": "Unauthorized"}), 401

    # Check if NGO is verified — if not, return empty with a notice
    conn = get_db()
    run_expiry(conn)
    cur = conn.cursor()
    cur.execute("SELECT verification_status FROM ngo_verification WHERE ngo_id=?", (session['user_id'],))
    ver_row = cur.fetchone()
    ngo_verified = ver_row and ver_row['verification_status'] == 'Verified'

    cur.execute("""
        SELECT fd.donation_id, fd.food_type, fd.quantity,
               fd.original_quantity, fd.accepted_quantity,
               fd.date_of_donation, fd.time,
               fd.cooked_at, fd.food_category,
               fd.food_photo_path,
               d.donor_name, d.contact_no AS donor_contact, d.address AS donor_address,
               d.hygiene_rating AS donor_rating, d.donor_type,
               dv.verification_status AS donor_fssai_status
        FROM food_donation fd
        LEFT JOIN donor d ON d.donor_id = fd.donor_id
        LEFT JOIN donor_verification dv ON dv.donor_id = d.donor_id
        WHERE fd.donation_status = 'Pending'
        ORDER BY fd.donation_id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    data = []
    for r in rows:
        photo_url = None
        if r['food_photo_path']:
            photo_url = f"/food-photo/{r['food_photo_path'].replace(os.sep, '/')}"
        data.append({
            "donation_id": r['donation_id'], "food_type": r['food_type'], "quantity": r['quantity'],
            "original_quantity": r['original_quantity'], "accepted_quantity": r['accepted_quantity'],
            "date_of_donation": str(r['date_of_donation']) if r['date_of_donation'] else None,
            "time": str(r['time']) if r['time'] else None,
            "cooked_at": r['cooked_at'],
            "food_category": r['food_category'],
            "food_photo_url": photo_url,
            "donor_name": r['donor_name'], "donor_contact": r['donor_contact'],
            "donor_address": r['donor_address'],
            "donor_rating": float(r['donor_rating'] or 0.0),
            "donor_type": r['donor_type'],
            "donor_fssai_verified": r['donor_fssai_status'] == 'Verified'
        })
    return jsonify({"success": True, "data": data, "ngo_verified": ngo_verified})


@app.route('/api/ngo/accept-donation', methods=['POST'])
def ngo_accept_donation():
    if not _is_ngo():
        return jsonify({"error": "Unauthorized"}), 401

    # Block unverified NGOs from accepting donations
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT verification_status FROM ngo_verification WHERE ngo_id=?", (session['user_id'],))
    ver_row = cur.fetchone()
    if not ver_row or ver_row['verification_status'] != 'Verified':
        conn.close()
        return jsonify({"error": "Your NGO must be verified by an administrator before accepting donations."}), 403

    d = request.get_json()
    donation_id = d.get('donation_id')
    ngo_id = session['user_id']
    raw_qty = d.get('accepted_qty')

    try:
        accepted_qty = int(raw_qty) if raw_qty is not None and str(raw_qty).strip() != '' else None
    except (ValueError, TypeError):
        conn.close()
        return jsonify({"error": "Invalid accepted_qty"}), 400

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
        cur.execute("""
            UPDATE food_donation
            SET quantity = ?,
                accepted_quantity = COALESCE(accepted_quantity, 0) + ?,
                original_quantity = ?
            WHERE donation_id = ?
        """, (remaining, accepted_qty, orig_qty, donation_id))

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

    cur.execute("""
        INSERT INTO pickup (time, status, otp_code, donation_id, volunteer_id)
        VALUES (DATETIME('now'), 'Pending', NULL, ?, NULL)
    """, (working_donation_id,))
    pickup_id = cur.lastrowid

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
    if not _is_ngo():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT dl.delivery_id, dl.delivery_status, dl.time,
               fd.food_type,  fd.quantity,
               fd.original_quantity, fd.parent_donation_id,
               fd.cooked_at, fd.food_category,
               d.donor_name,  d.address   AS donor_address,
               v.name         AS volunteer_name,
               v.contact_no   AS volunteer_contact,
               v.vehicle_type,
               vv.verification_status AS vol_verified,
               vv.vehicle_reg_no,
               p.status       AS pickup_status,
               p.otp_code,
               p.pickup_id,
               fd.donation_id,
               d.hygiene_rating AS donor_rating,
               dv.verification_status AS donor_fssai_status
        FROM delivery dl
        JOIN pickup        p  ON p.pickup_id   = dl.pickup_id
        JOIN food_donation fd ON fd.donation_id = p.donation_id
        JOIN donor         d  ON d.donor_id     = fd.donor_id
        LEFT JOIN volunteer v ON v.volunteer_id = p.volunteer_id
        LEFT JOIN volunteer_verification vv ON vv.volunteer_id = v.volunteer_id
        LEFT JOIN donor_verification dv ON dv.donor_id = d.donor_id
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
            "cooked_at": r['cooked_at'], "food_category": r['food_category'],
            "donor_name": r['donor_name'], "donor_address": r['donor_address'],
            "volunteer_name": r['volunteer_name'], "volunteer_contact": r['volunteer_contact'],
            "vehicle_type": r['vehicle_type'],
            "vol_verified": r['vol_verified'] == 'Verified' if r['vol_verified'] else False,
            "vehicle_reg_no": r['vehicle_reg_no'],
            "pickup_status": r['pickup_status'],
            "otp_code": r['otp_code'], "pickup_id": r['pickup_id'], "donation_id": r['donation_id'],
            "donor_rating": float(r['donor_rating'] or 0.0),
            "donor_fssai_verified": r['donor_fssai_status'] == 'Verified'
        })
    return jsonify({"success": True, "data": data})


@app.route('/api/ngo/mark-received', methods=['POST'])
def ngo_mark_received():
    if not _is_ngo():
        return jsonify({"error": "Unauthorized"}), 401
    d = request.get_json()
    delivery_id = d.get('delivery_id')
    pickup_id = d.get('pickup_id')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE delivery SET delivery_status='Delivered' WHERE delivery_id=? AND ngo_id=?",
                (delivery_id, session['user_id']))
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

    # Trigger automatic rewards processing for completed donation & delivery
    try:
        cur.execute("SELECT donation_id FROM pickup WHERE pickup_id=?", (pickup_id,))
        don_row = cur.fetchone()
        if don_row and don_row['donation_id']:
            process_donation_completed(conn, don_row['donation_id'])
        process_delivery_completed(conn, pickup_id)
        conn.commit()
    except Exception as e:
        print(f"[Rewards Error in ngo_mark_received]: {e}")

    conn.close()
    return jsonify({"success": True, "message": "Marked as received!"})


@app.route('/api/ngo/feedback', methods=['POST'])
def submit_ngo_feedback():
    if not _is_ngo():
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

    cur.execute("""
        SELECT AVG(hygiene_score) FROM feedback WHERE donor_id = ? AND from_ngo = 1
    """, (donor_id,))
    avg_score = cur.fetchone()[0] or 5.0

    cur.execute("UPDATE donor SET hygiene_rating = ? WHERE donor_id = ?",
                (round(float(avg_score), 1), donor_id))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Feedback & rating submitted successfully!"})


@app.route('/api/ngo/feedback-given', methods=['GET'])
def ngo_feedback_given():
    if not _is_ngo():
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
            "rating": row['rating'], "comments": row['comments'],
            "hygiene_score": row['hygiene_score'],
            "feedback_date": str(row['feedback_date']),
            "food_type": row['food_type'], "donor_name": row['donor_name']
        })
    return jsonify({"success": True, "data": result})


@app.route('/api/ngo/wasted-donations')
def ngo_wasted_donations():
    if not _is_ngo():
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
            "quantity": r['quantity'],
            "available_until": str(r['time']) if r['time'] else None,
            "date_of_donation": str(r['date_of_donation']) if r['date_of_donation'] else None,
            "original_quantity": r['original_quantity'],
            "accepted_quantity": r['accepted_quantity']
        })
    return jsonify({"success": True, "data": data})


# ═════════════════════════════════════════════════════════════
# API — VOLUNTEER ENDPOINTS
# ═════════════════════════════════════════════════════════════

@app.route('/api/volunteer/profile')
def volunteer_profile():
    if not _is_volunteer():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT v.name, v.contact_no, v.vehicle_type, v.availability_status,
               vv.verification_status AS ver_status,
               vv.vehicle_reg_no, vv.emergency_contact_name, vv.emergency_contact_phone,
               vv.rejection_reason
        FROM volunteer v
        LEFT JOIN volunteer_verification vv ON vv.volunteer_id = v.volunteer_id
        WHERE v.volunteer_id=?
    """, (session['user_id'],))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "name": row['name'],
        "contact_no": row['contact_no'],
        "vehicle_type": row['vehicle_type'],
        "availability_status": row['availability_status'],
        "ver_status": row['ver_status'] or 'Not Submitted',
        "vehicle_reg_no": row['vehicle_reg_no'],
        "emergency_contact_name": row['emergency_contact_name'],
        "emergency_contact_phone": row['emergency_contact_phone'],
        "rejection_reason": row['rejection_reason']
    })


@app.route('/api/volunteer/update', methods=['POST'])
def update_volunteer_profile():
    if not _is_volunteer():
        return jsonify({"error": "Unauthorized"}), 401
    d = request.get_json()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE volunteer SET name=?, contact_no=?, vehicle_type=?, availability_status=? WHERE volunteer_id=?",
        (d.get('name'), d.get('contact_no'), d.get('vehicle_type'),
         d.get('availability_status'), session['user_id'])
    )
    conn.commit()
    conn.close()
    session['user_name'] = d.get('name')
    return jsonify({"success": True, "message": "Profile updated"})


@app.route('/api/volunteer/submit-verification', methods=['POST'])
def volunteer_submit_verification():
    if not _is_volunteer():
        return jsonify({"error": "Unauthorized"}), 401

    volunteer_id = session['user_id']
    vehicle_reg_no = request.form.get('vehicle_reg_no', '').strip() or None
    emergency_contact_name = request.form.get('emergency_contact_name', '').strip() or None
    emergency_contact_phone = request.form.get('emergency_contact_phone', '').strip() or None

    photo_id = request.files.get('photo_id')
    selfie = request.files.get('selfie')
    dl_file = request.files.get('driving_licence')

    # Photo ID is required
    if not photo_id or photo_id.filename == '':
        return jsonify({"error": "Photo ID document is required"}), 400

    # Selfie is required
    if not selfie or selfie.filename == '':
        return jsonify({"error": "Selfie is required for identity review"}), 400

    photo_id_path = _save_private_file(photo_id, 'volunteer_docs', ALLOWED_DOC_EXTENSIONS)
    if photo_id_path is None:
        return jsonify({"error": "Invalid Photo ID file. Allowed: PDF, JPG, PNG. Max 5MB."}), 400

    selfie_path = _save_private_file(selfie, 'volunteer_docs', ALLOWED_PHOTO_EXTENSIONS)
    if selfie_path is None:
        return jsonify({"error": "Invalid selfie file. Allowed: JPG, PNG, WEBP. Max 5MB."}), 400

    dl_path = None
    if dl_file and dl_file.filename != '':
        dl_path = _save_private_file(dl_file, 'volunteer_docs', ALLOWED_DOC_EXTENSIONS)
        if dl_path is None:
            return jsonify({"error": "Invalid driving licence file. Allowed: PDF, JPG, PNG. Max 5MB."}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM volunteer_verification WHERE volunteer_id=?", (volunteer_id,))
    existing = cur.fetchone()
    now = datetime.now().isoformat()

    if existing:
        cur.execute("""
            UPDATE volunteer_verification
            SET photo_id_path=?, selfie_path=?,
                vehicle_reg_no=?, dl_path=COALESCE(?, dl_path),
                emergency_contact_name=?, emergency_contact_phone=?,
                verification_status='Pending', rejection_reason=NULL, submitted_at=?
            WHERE volunteer_id=?
        """, (photo_id_path, selfie_path, vehicle_reg_no, dl_path,
              emergency_contact_name, emergency_contact_phone, now, volunteer_id))
    else:
        cur.execute("""
            INSERT INTO volunteer_verification
            (volunteer_id, photo_id_path, selfie_path, vehicle_reg_no, dl_path,
             emergency_contact_name, emergency_contact_phone, verification_status, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?)
        """, (volunteer_id, photo_id_path, selfie_path, vehicle_reg_no, dl_path,
              emergency_contact_name, emergency_contact_phone, now))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Verification submitted. Awaiting admin review."})


@app.route('/api/volunteer/verification-status')
def volunteer_verification_status():
    if not _is_volunteer():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT verification_status, rejection_reason, submitted_at,
               vehicle_reg_no, emergency_contact_name, emergency_contact_phone
        FROM volunteer_verification WHERE volunteer_id=?
    """, (session['user_id'],))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({
            "success": True,
            "volunteer_id": session['user_id'],
            "verification": {"verification_status": "None"},
            "status": "Not Submitted"
        })
    return jsonify({
        "success": True,
        "volunteer_id": session['user_id'],
        "verification": {
            "verification_status": row['verification_status'],
            "rejection_reason": row['rejection_reason'],
            "vehicle_reg_no": row['vehicle_reg_no'],
            "emergency_contact_name": row['emergency_contact_name'],
            "emergency_contact_phone": row['emergency_contact_phone'],
            "submitted_at": str(row['submitted_at'])
        },
        "status": row['verification_status'],
        "rejection_reason": row['rejection_reason'],
        "submitted_at": str(row['submitted_at'])
    })


@app.route('/api/volunteer/card/<int:volunteer_id>')
def volunteer_card(volunteer_id):
    """Return volunteer profile card data — visible only to authenticated donors."""
    if not _is_donor():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT v.name, v.vehicle_type, v.contact_no,
               vv.verification_status, vv.vehicle_reg_no
        FROM volunteer v
        LEFT JOIN volunteer_verification vv ON vv.volunteer_id = v.volunteer_id
        WHERE v.volunteer_id=?
    """, (volunteer_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Volunteer not found"}), 404
    card_data = {
        "name": row['name'],
        "vehicle_type": row['vehicle_type'],
        "contact_no": row['contact_no'],
        "verified": row['verification_status'] == 'Verified',
        "verification_status": row['verification_status'] or 'Pending',
        "vehicle_reg_no": row['vehicle_reg_no']
        # No photo, selfie, driving licence, or emergency contacts exposed
    }
    return jsonify({
        "success": True,
        "card": card_data,
        **card_data
    })


@app.route('/api/volunteer/stats')
def volunteer_stats():
    if not _is_volunteer():
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
    if not _is_volunteer():
        return jsonify({"error": "Unauthorized"}), 401

    vid = session['user_id']
    conn = get_db()
    cur = conn.cursor()

    # Open Pickups (Unassigned)
    cur.execute("""
        SELECT p.pickup_id,   p.time,         p.status,      p.otp_code,
               fd.food_type,  fd.quantity,    fd.food_category,
               d.donor_name,  d.contact_no    AS donor_contact,
               d.address      AS donor_address,
               n.ngo_name,    n.address       AS ngo_address,
               n.contact_no   AS ngo_contact,
               dl.delivery_id, dl.delivery_status,
               d.hygiene_rating AS donor_rating,
               dv.verification_status AS donor_fssai_status
        FROM pickup p
        JOIN food_donation fd ON fd.donation_id = p.donation_id
        JOIN donor         d  ON d.donor_id     = fd.donor_id
        LEFT JOIN delivery dl ON dl.pickup_id   = p.pickup_id
        LEFT JOIN ngo      n  ON n.ngo_id       = dl.ngo_id
        LEFT JOIN donor_verification dv ON dv.donor_id = d.donor_id
        WHERE p.volunteer_id IS NULL AND p.status = 'Pending'
        ORDER BY p.pickup_id DESC
    """)
    open_rows = cur.fetchall()

    # My Claimed Pickups
    cur.execute("""
        SELECT p.pickup_id,   p.time,         p.status,      p.otp_code,
               fd.food_type,  fd.quantity,    fd.food_category,
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
            "food_category": r['food_category'],
            "donor_name": r['donor_name'], "donor_contact": r['donor_contact'],
            "donor_address": r['donor_address'],
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
    if not _is_volunteer():
        return jsonify({"error": "Unauthorized"}), 401

    # Block unverified volunteers from accepting pickups
    vid = session['user_id']
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT verification_status FROM volunteer_verification WHERE volunteer_id=?", (vid,))
    ver_row = cur.fetchone()
    if not ver_row or ver_row['verification_status'] != 'Verified':
        conn.close()
        return jsonify({"error": "You must be verified by an administrator before accepting pickups."}), 403

    d = request.get_json()
    pickup_id = d.get('pickup_id')

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
    if not _is_volunteer():
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
        cur.execute("UPDATE volunteer SET availability_status='Available' WHERE volunteer_id=?",
                    (session['user_id'],))
        cur.execute("""
            UPDATE food_donation SET donation_status='Completed'
            WHERE donation_id = (SELECT donation_id FROM pickup WHERE pickup_id=?)
        """, (pickup_id,))
        conn.commit()

        # Trigger automatic rewards processing for completed delivery & donation
        try:
            cur.execute("SELECT donation_id FROM pickup WHERE pickup_id=?", (pickup_id,))
            don_row = cur.fetchone()
            if don_row and don_row['donation_id']:
                process_donation_completed(conn, don_row['donation_id'])
            process_delivery_completed(conn, pickup_id)
            conn.commit()
        except Exception as e:
            print(f"[Rewards Error in volunteer pickup_status]: {e}")

    conn.close()

    return jsonify({"success": True, "message": f"Pickup status updated to {status}"})


@app.route('/api/volunteer/wasted-donations')
def volunteer_wasted_donations():
    if not _is_volunteer():
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
            "quantity": r['quantity'],
            "available_until": str(r['time']) if r['time'] else None,
            "date_of_donation": str(r['date_of_donation']) if r['date_of_donation'] else None,
            "original_quantity": r['original_quantity'],
            "accepted_quantity": r['accepted_quantity']
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


# ═════════════════════════════════════════════════════════════
# REWARDS AND RECOGNITION API ROUTES
# ═════════════════════════════════════════════════════════════

@app.route('/api/rewards/summary')
def rewards_summary():
    if 'user_id' not in session or 'role' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    role = session['role']
    uid = session['user_id']

    if role == 'donor':
        data = get_donor_impact_summary(conn, uid)
    elif role == 'volunteer':
        data = get_volunteer_impact_summary(conn, uid)
    elif role == 'ngo':
        data = get_ngo_impact_summary(conn, uid)
    else:
        conn.close()
        return jsonify({"error": "Invalid role"}), 400

    conn.close()
    return jsonify({"success": True, "data": data, "role": role})


@app.route('/api/rewards/leaderboard')
def rewards_leaderboard():
    role = request.args.get('role', session.get('role', 'donor')).lower()
    if role not in ('donor', 'volunteer'):
        role = 'donor'
    lb_type = request.args.get('type', 'monthly').lower()
    if lb_type not in ('monthly', 'all_time'):
        lb_type = 'monthly'

    conn = get_db()
    board = get_leaderboard(conn, role, lb_type)
    conn.close()

    return jsonify({
        "success": True,
        "role": role,
        "type": lb_type,
        "leaderboard": board
    })


@app.route('/api/rewards/leaderboard/opt-in', methods=['POST'])
def rewards_leaderboard_opt_in():
    if 'user_id' not in session or 'role' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    role = session['role']
    if role not in ('donor', 'volunteer'):
        return jsonify({"error": "Role not applicable"}), 400

    d = request.get_json() or {}
    opt_in = 1 if d.get('opt_in', True) else 0

    conn = get_db()
    get_or_create_account(conn, session['user_id'], role)
    cur = conn.cursor()
    cur.execute('''
        UPDATE reward_accounts
        SET leaderboard_opt_in=?
        WHERE user_id=? AND user_role=?
    ''', (opt_in, session['user_id'], role))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "leaderboard_opt_in": bool(opt_in)})


@app.route('/api/rewards/catalog')
def rewards_catalog():
    return jsonify({"success": True, "catalog": REWARD_CATALOG_ITEMS})


@app.route('/api/rewards/redeem', methods=['POST'])
def rewards_redeem():
    if 'user_id' not in session or 'role' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    role = session['role']
    if role not in ('donor', 'volunteer'):
        return jsonify({"error": "Rewards redemption is available for donors and volunteers."}), 400

    d = request.get_json() or {}
    item_key = d.get('item_key')
    if not item_key:
        return jsonify({"success": False, "error": "Item key is required"}), 400

    conn = get_db()
    res = redeem_reward(conn, session['user_id'], role, item_key, recipient_name=session.get('user_name'))
    conn.close()

    status_code = 200 if res.get('success') else 400
    return jsonify(res), status_code


@app.route('/api/rewards/history')
def rewards_history():
    if 'user_id' not in session or 'role' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    role = session['role']
    if role not in ('donor', 'volunteer'):
        return jsonify({"error": "Not applicable"}), 400

    conn = get_db()
    history = get_user_rewards_history(conn, session['user_id'], role)
    conn.close()

    return jsonify({"success": True, "history": history})


@app.route('/api/rewards/certificates')
def rewards_certificates():
    if 'user_id' not in session or 'role' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    role = session['role']
    if role not in ('donor', 'volunteer'):
        return jsonify({"error": "Not applicable"}), 400

    conn = get_db()
    certs = get_user_certificates(conn, session['user_id'], role)
    conn.close()

    return jsonify({"success": True, "certificates": certs})


@app.route('/api/rewards/redemptions')
def rewards_redemptions_list():
    if 'user_id' not in session or 'role' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    role = session['role']
    if role not in ('donor', 'volunteer'):
        return jsonify({"error": "Not applicable"}), 400

    conn = get_db()
    redemptions = get_user_redemptions(conn, session['user_id'], role)
    conn.close()

    return jsonify({"success": True, "redemptions": redemptions})


@app.route('/api/rewards/certificates/<cert_code>/download')
def download_certificate(cert_code):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM reward_certificates WHERE cert_code=?", (cert_code,))
    cert = cur.fetchone()
    conn.close()

    if not cert:
        return jsonify({"error": "Certificate not found"}), 404

    # Security check: must be owner or admin
    is_owner = ('user_id' in session and session.get('user_id') == cert['user_id']
                and session.get('role') == cert['user_role'])
    if not is_owner and not _is_admin():
        return jsonify({"error": "Unauthorized to access this certificate"}), 403

    pdf_filename = cert['pdf_path'] or f"{cert_code}.pdf"
    pdf_full_path = os.path.join(CERTIFICATES_DIR, pdf_filename)

    # If file was deleted or not generated, regenerate on the fly
    if not os.path.exists(pdf_full_path):
        cert_data = {
            "cert_code": cert['cert_code'],
            "recipient_name": cert['recipient_name'],
            "milestone_title": cert['milestone_title'],
            "milestone_count": cert['milestone_count'],
            "role_label": "Food Donations" if cert['user_role'] == 'donor' else "Food Deliveries",
            "issued_date": cert['issued_date'],
            "cert_type": "Official Milestone Issue" if cert['cert_type'] == 'milestone' else "Points-Based Recognition Reward"
        }
        _build_pdf_certificate(pdf_full_path, cert_data)

    return send_file(
        pdf_full_path,
        as_attachment=True,
        download_name=f"{cert_code}.pdf",
        mimetype='application/pdf'
    )


@app.route('/api/rewards/notifications')
def rewards_notifications():
    if 'user_id' not in session or 'role' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT notification_id, title, message, event_type, is_read, created_at
        FROM reward_notifications
        WHERE user_id=? AND user_role=?
        ORDER BY notification_id DESC
        LIMIT 20
    ''', (session['user_id'], session['role']))
    rows = [dict(r) for r in cur.fetchall()]

    # Mark as read
    cur.execute('''
        UPDATE reward_notifications
        SET is_read=1
        WHERE user_id=? AND user_role=? AND is_read=0
    ''', (session['user_id'], session['role']))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "notifications": rows})


@app.route('/api/ngo/impact-summary')
def ngo_impact_route():
    if not _is_ngo():
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    data = get_ngo_impact_summary(conn, session['user_id'])
    conn.close()
    return jsonify({"success": True, "data": data})


@app.route('/api/ngo/confirm-distribution', methods=['POST'])
def ngo_confirm_distribution_route():
    if not _is_ngo():
        return jsonify({"error": "Unauthorized"}), 401

    d = request.get_json() or {}
    delivery_id = d.get('delivery_id')
    meals_distributed = d.get('meals_distributed', 0)
    beneficiary_group = d.get('beneficiary_group', 'Local Community')
    notes = d.get('notes', '')
    distributed_date = d.get('distributed_date', '')

    try:
        meals_distributed = int(meals_distributed)
        delivery_id = int(delivery_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid delivery ID or meals distributed"}), 400

    conn = get_db()
    res = confirm_ngo_distribution(
        conn, session['user_id'], delivery_id, meals_distributed,
        beneficiary_group, notes, distributed_date
    )
    conn.close()

    status_code = 200 if res.get('success') else 400
    return jsonify(res), status_code


@app.route('/api/admin/rewards/revoke', methods=['POST'])
def admin_revoke_rewards_route():
    if not _is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    d = request.get_json() or {}
    activity_type = d.get('activity_type', '').lower()
    activity_id = d.get('activity_id')
    reason = d.get('reason', '').strip()

    if activity_type not in ('donation', 'delivery') or not activity_id or not reason:
        return jsonify({"success": False, "error": "activity_type (donation/delivery), activity_id, and reason required"}), 400

    try:
        activity_id = int(activity_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid activity_id"}), 400

    conn = get_db()
    res = admin_revoke_activity_points(
        conn, session.get('user_name', 'admin'), activity_type, activity_id, reason
    )
    conn.close()

    status_code = 200 if res.get('success') else 400
    return jsonify(res), status_code


@app.route('/api/admin/rewards/audit-log')
def admin_rewards_audit_log():
    if not _is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT rt.*,
               CASE
                 WHEN rt.user_role = 'donor' THEN (SELECT donor_name FROM donor WHERE donor_id=rt.user_id)
                 WHEN rt.user_role = 'volunteer' THEN (SELECT name FROM volunteer WHERE volunteer_id=rt.user_id)
                 ELSE 'Unknown'
               END AS user_name
        FROM reward_transactions rt
        ORDER BY rt.transaction_id DESC
        LIMIT 100
    ''')
    transactions = [dict(r) for r in cur.fetchall()]
    conn.close()

    return jsonify({"success": True, "audit_log": transactions})


@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "service": "Mobile FoodBridge App Backend"})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 60)
    print(f"  Mobile FoodBridge App Backend Running on port {port}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=False)
