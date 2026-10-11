# 🥗 FoodBridge Mobile — Trust, Safety, Verification & Rewards Platform

FoodBridge Mobile is a community food-rescue application connecting Food Donors (Restaurants, Caterers, Hotels, Individuals), NGOs / Relief Shelters, and Delivery Volunteers to eliminate surplus food waste and feed those in need.

This release incorporates an enterprise-grade **Trust, Safety, and Verification System** and a complete **Rewards & Recognition System** featuring FoodBridge Points, Achievement Badges, Leaderboards, PDF Appreciation Certificates, Monthly Donation Streaks, Personal Impact Dashboards, Digital Rewards Redemption Store, NGO Impact Recognition & Distribution Confirmations, In-app Notifications, and an Admin Points Audit/Revocation Ledger.

---

## 🌟 Key Features & Systems

### 1. 🏆 Rewards & Recognition System
- **FoodBridge Points Engine**:
  - **Donors**: 100 points for first completed donation, 50 points for subsequent completed donations. Milestone bonuses: +150 at 5 donations, +300 at 10, +500 at 25, +1000 at 50 donations.
  - **Volunteers**: 100 points for first completed delivery, 75 points for subsequent deliveries. Milestone bonuses: +200 at 5 deliveries, +400 at 10, +750 at 25 deliveries.
  - **Audit & Anti-Gaming**: Only completed donations and delivered pickups trigger rewards. Duplicate requests, cancellations, or incomplete deliveries award zero points.
- **Monthly Donation Streaks (Donors)**:
  - Tracks continuous monthly donations across distinct calendar months.
  - Streak bonuses: 2 consecutive months (+100 pts), 3 months (+200 pts), 6 months (+500 pts), 12 months (Consistency Champion badge + 1000 pts).
  - Skips reset the active streak while preserving the longest streak record.
- **Achievement Badges**:
  - Distinct badge systems for Donors, Volunteers, NGOs, and special achievements.
  - Special profile badges: *FSSAI Verified Hero*, *Verified Relief Partner*, *Elite Speed Courier*.
- **Public Leaderboards with Privacy Controls**:
  - Top Donors & Top Volunteers leaderboards (Monthly and All-Time rankings).
  - Strict privacy: Never reveals phone numbers, email addresses, or document data.
  - One-click privacy opt-out toggle (`/api/rewards/leaderboard/opt-in`).
- **High-Quality PDF Appreciation Certificates**:
  - Generated dynamically via ReportLab with formal borders, gold/teal branding, unique verification codes, and download access.
  - Milestone certificates (e.g., Bronze, Silver, Gold, Platinum) and on-demand redeemed certificates.
- **Digital Rewards Redemption Store**:
  - Point-based digital catalog (Profile Badges, Trees Planted in Honor, Featured Sponsor Spotlight, Certificate Downloads).
  - Atomic point deductions ensuring balances never go negative.
- **NGO Impact Recognition & Distribution Confirmations**:
  - Total meals distributed, families supported, and people nourished counters.
  - Verification workflow with optional photo uploads to confirm food distributions to community beneficiaries.
- **In-App Rewards Notifications**:
  - Real-time alerts for earned points, newly unlocked badges, and milestones.
- **Admin Rewards Audit & Points Revocation**:
  - Complete immutable audit ledger of all reward transactions.
  - Administrator revocation modal at `/admin` to revert points from fraudulent or cancelled activities with audit logging.
- **Android Native Download Support**:
  - `MainActivity.java` integrates `DownloadManager` for automatic PDF certificate downloads in Android WebView apps with notification and cookie handling.

---

### 2. 🏢 Donor Verification (FSSAI Compliance)
- **Business vs. Individual Donors**: Uses `donor_type` to differentiate businesses (Restaurants, Caterers, Hotels) from individual citizens.
- **14-Digit FSSAI License Validation**: Server-side and client-side validation ensuring valid 14-digit numeric FSSAI registration numbers.
- **FSSAI Certificate Upload**: Business donors can upload their official FSSAI registration documents (PDF/JPG/PNG).
- **"FSSAI Verified" Badge**: Displayed in donor profiles and feeds only after an administrator verifies and approves documents.
- **Preserved Hygiene Ratings**: Existing 5-star donor hygiene ratings and feedback remain intact and prominently visible.

---

### 3. 🏛️ NGO Verification (Darpan ID & Registration)
- **NGO Darpan ID**: Mandatory Darpan ID verification for NGOs operating in India.
- **Registration Certificate Upload**: Document upload supporting Trust, Society, or Section 8 Company registrations.
- **Tax Exemptions**: Optional 12A and 80G certificate registration numbers.
- **Responsible Contact Details**: Contact person name and verified phone number.
- **Unverified Access Prevention**: Unverified NGOs are strictly blocked from accepting food donations until approved by an administrator.
- **"NGO Verified" Badge**: Visible to donors and volunteers once approved.

---

### 4. 🚴 Volunteer Verification & Safety (KYC & Profile Card)
- **Identity KYC**: Photo ID (Voter ID, College ID, Driving Licence) and selfie upload for identity review.
- **Vehicle Registration & Driving Licence**: Optional vehicle number and DL upload for volunteers delivering via bike, scooter, car, or van.
- **Emergency Contacts**: Optional emergency contact name and phone number.
- **Aadhaar Privacy**: Full Aadhaar numbers are never stored or requested, adhering to Indian data protection principles.
- **Unverified Pickup Blocking**: Unverified volunteers are prevented from claiming pickup tasks in both frontend and backend.
- **Volunteer Profile Card**: Donors can view the assigned volunteer's name, profile photo, vehicle number, and verification status before handover.
- **Security OTP Delivery**: Preserves and reinforces the 4-digit pickup code handoff workflow between donor, volunteer, and NGO.

---

### 5. 🛡️ Dedicated Admin Verification Dashboard (`/admin`)
- Accessible at `/admin` with secure administrator authentication.
- Verification review queues for Pending Donors, NGOs, and Volunteers with custom rejection reasons.
- **Rewards Audit & Revocation Tab**: View points ledger, search user accounts, and execute point revocations with mandatory reason logging.
- Secure private document and certificate viewer (`/admin/doc/<path>`).

---

### 6. 🔒 Private Document Security & Privacy
- Verification documents, certificates, and selfies are kept in private storage (`private_uploads/`), outside publicly accessible web roots.
- Role-based authorization: Only verified administrators can access applicant identity documents.
- Path-traversal and file-extension protections (`.pdf`, `.jpg`, `.jpeg`, `.png`, `.webp`, max 5MB).
- No sensitive user credentials or full Aadhaar numbers stored or leaked across API endpoints.

---

## 🏗️ Project Architecture

```
MobileApplication/
├── app.py                      # Flask backend API, authentication, rewards & verification routes
├── rewards_service.py          # Rewards, badges, streak, PDF certificate & audit service
├── database.py                 # SQLite schema definitions & safe backward-compatible migrations
├── templates/
│   ├── index.html              # Preserved mobile app UI with rewards & verification views
│   └── admin.html              # Dedicated Admin Portal with Verification & Rewards Audit tabs
├── static/
│   ├── css/mobile.css          # Mobile styling + rewards badges, leaderboards, certificates
│   ├── js/app.js               # Frontend application controller & rewards interactions
│   └── img/                    # Static brand assets
├── android-project/            # Native Android Studio project with DownloadManager integration
├── private_uploads/            # Secure document & PDF certificate storage
│   ├── certificates/           # Generated PDF Appreciation Certificates
│   ├── donor_docs/
│   ├── ngo_docs/
│   ├── volunteer_docs/
│   ├── food_photos/
│   └── distribution_photos/
├── test_rewards_system.py      # Automated test suite for Rewards & Recognition System
├── test_verification_system.py # Comprehensive verification and safety test suite
├── requirements.txt            # Python dependencies (includes reportlab>=4.0.0)
├── Procfile / wsgi.py          # Production WSGI deployment entrypoints
├── capacitor.config.json       # Mobile wrapper configuration
└── DEPLOYMENT_AND_APK_GUIDE.md # Guide for Cloud hosting and APK generation
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.9+ installed
- Node.js (optional, only if rebuilding Capacitor assets)

### 2. Setup Virtual Environment & Dependencies
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS / Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Initialize / Migrate Database
The application automatically executes backward-compatible database migrations on startup. To verify or run migrations manually:
```bash
python3 -c "import database; database.init_db(); print('Database migrated successfully!')"
```

### 4. Run the Application
```bash
python3 app.py
```
Open your browser at:
- **Mobile Web Application**: [http://127.0.0.1:5000](http://127.0.0.1:5000)
- **Admin Portal**: [http://127.0.0.1:5000/admin](http://127.0.0.1:5000/admin)

---

## 🔑 Default Accounts & Credentials

### Administrator Account
- **URL**: `http://127.0.0.1:5000/admin`
- **Username**: `admin`
- **Password**: `FoodBridgeAdmin2026!`

*(Note: In production, configure strong administrator credentials via environment variables)*

### Demo Accounts
- **Demo Donor**: `Fresh Bites Bakery` / `donor123` (Business Donor)
- **Demo NGO**: `Hope Haven Shelter` / `donor123`
- **Demo Volunteer**: `Alex Rivera` / `donor123`

---

## 🧪 Automated Testing

Both comprehensive test suites validate the platform with 100% test pass rates:

```bash
# 1. Run Rewards and Recognition Test Suite (12 test scenarios)
python3 -m unittest test_rewards_system.py

# 2. Run Verification and Safety Test Suite (8 test scenarios)
python3 -m unittest test_verification_system.py
```

### Rewards Test Coverage:
- ✅ Donor points calculation (first donation 100 pts, subsequent 50 pts, milestone bonuses).
- ✅ Volunteer points calculation (first delivery 100 pts, subsequent 75 pts, milestone bonuses).
- ✅ Badge unlocking across donors, volunteers, and NGOs.
- ✅ Duplicate completion prevention (idempotent points processing).
- ✅ Cancelled donations and failed deliveries award zero points.
- ✅ Monthly donation streak calculations and streak bonuses.
- ✅ Leaderboard ranking display and privacy opt-out toggling.
- ✅ PDF certificate generation (ReportLab) and authenticated secure downloading.
- ✅ Digital rewards catalog redemption with atomic balance deductions and anti-overdraft.
- ✅ NGO distribution confirmation, meal counters, and impact badge unlocking.
- ✅ In-app notifications logging for rewards milestones.
- ✅ Admin points revocation with audit transaction ledger recording.

---

## 📦 Database Migration Notes

- **Existing Database Compatibility**: `database.py` executes non-destructive `PRAGMA table_info` checks and `ALTER TABLE ADD COLUMN` operations. Existing rows in `donor`, `ngo`, `volunteer`, `food_donation`, `pickup`, and `delivery` are fully preserved.
- **Fresh Database Compatibility**: If `food_db.db` does not exist, `init_db()` creates all original tables alongside the verification and rewards tables and seeds default demo records.
- **Safe Distribution**: The distributable ZIP does not bundle live personal databases. When deploying on a new machine, `database.init_db()` will automatically construct the required schema.

---

## 📱 Android Build & APK Generation

Refer to `DEPLOYMENT_AND_APK_GUIDE.md` for complete instructions on building the Android APK using Android Studio, Gradle, or GitHub Actions. Native PDF certificate download handling is configured in `MainActivity.java` via Android's `DownloadManager`.

