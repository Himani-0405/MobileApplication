"""
FoodBridge Rewards & Recognition System Service
Handles:
- FoodBridge Points (FB Points) calculation & atomic ledger transactions
- Achievement Badges (Donors, Volunteers, NGOs, Streaks)
- Downloadable Appreciation Certificates (PDF generation via ReportLab)
- Monthly Donation Streaks
- Leaderboards (Monthly & All-Time, opt-in privacy)
- Personal Impact Metrics
- Digital Rewards Redemption Store
- NGO Impact Recognition & Distribution Confirmations
- Audit records & Admin Points Revocation
- In-App Reward Notifications
"""

import os
import io
import math
import uuid
import sqlite3
from datetime import datetime, date
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas

CERTIFICATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'private_uploads', 'certificates')
os.makedirs(CERTIFICATES_DIR, exist_ok=True)

# ─── Badge Definitions ─────────────────────────────────────────────────────────
DONOR_BADGES = [
    {"key": "donor_first_step", "name": "First Step", "description": "Complete 1 donation", "threshold": 1, "icon": "ri-footprint-line"},
    {"key": "donor_bronze", "name": "Bronze Donor", "description": "Complete 5 donations", "threshold": 5, "icon": "ri-medal-line"},
    {"key": "donor_silver", "name": "Silver Donor", "description": "Complete 10 donations", "threshold": 10, "icon": "ri-medal-fill"},
    {"key": "donor_gold", "name": "Gold Donor", "description": "Complete 25 donations", "threshold": 25, "icon": "ri-trophy-line"},
    {"key": "donor_platinum", "name": "Platinum Donor", "description": "Complete 50 donations", "threshold": 50, "icon": "ri-trophy-fill"},
    {"key": "donor_food_hero", "name": "Food Hero", "description": "Complete 100 donations", "threshold": 100, "icon": "ri-vip-crown-fill"}
]

VOLUNTEER_BADGES = [
    {"key": "vol_first_ride", "name": "First Ride", "description": "Complete 1 delivery", "threshold": 1, "icon": "ri-e-bike-2-line"},
    {"key": "vol_helping_hand", "name": "Helping Hand", "description": "Complete 5 deliveries", "threshold": 5, "icon": "ri-hand-heart-line"},
    {"key": "vol_delivery_star", "name": "Delivery Star", "description": "Complete 10 deliveries", "threshold": 10, "icon": "ri-star-smile-fill"},
    {"key": "vol_rescue_hero", "name": "Food Rescue Hero", "description": "Complete 25 deliveries", "threshold": 25, "icon": "ri-shield-star-line"},
    {"key": "vol_community_champion", "name": "Community Champion", "description": "Complete 50 deliveries", "threshold": 50, "icon": "ri-award-fill"}
]

NGO_BADGES = [
    {"key": "ngo_community_supporter", "name": "Community Supporter", "description": "Successfully distribute 100 meals", "threshold": 100, "metric": "meals", "icon": "ri-restaurant-line"},
    {"key": "ngo_reliable_partner", "name": "Reliable Partner", "description": "Complete 25 verified food distributions", "threshold": 25, "metric": "distributions", "icon": "ri-checkbox-circle-line"},
    {"key": "ngo_impact_partner", "name": "Community Impact Partner", "description": "Complete 50 verified food distributions", "threshold": 50, "metric": "distributions", "icon": "ri-heart-pulse-fill"},
    {"key": "ngo_distribution_champion", "name": "Food Distribution Champion", "description": "Complete 100 verified food distributions", "threshold": 100, "metric": "distributions", "icon": "ri-trophy-fill"}
]

STREAK_BADGES = [
    {"key": "streak_consistency_champion", "name": "Consistency Champion", "description": "12 consecutive months of donations", "threshold": 12, "icon": "ri-fire-fill"}
]

REWARD_CATALOG_ITEMS = [
    {
        "key": "item_card_500",
        "name": "Digital Appreciation Card",
        "points_cost": 500,
        "description": "Personalized digital card honoring your community contribution.",
        "item_type": "appreciation_card"
    },
    {
        "key": "item_badge_1000",
        "name": "Special Profile Badge",
        "points_cost": 1000,
        "description": "Exclusive 'Eco Supporter' recognition badge displayed on your profile.",
        "item_type": "profile_badge"
    },
    {
        "key": "item_cert_bronze_2000",
        "name": "Bronze Appreciation Certificate",
        "points_cost": 2000,
        "description": "Points-based Bronze recognition certificate downloadable as PDF.",
        "item_type": "certificate_bronze"
    },
    {
        "key": "item_cert_gold_5000",
        "name": "Gold Appreciation Certificate",
        "points_cost": 5000,
        "description": "Points-based Gold recognition certificate downloadable as PDF.",
        "item_type": "certificate_gold"
    },
    {
        "key": "item_hero_10000",
        "name": "Community Hero Recognition",
        "points_cost": 10000,
        "description": "Honorary Community Hero recognition badge & hall-of-fame title.",
        "item_type": "community_hero"
    }
]

# Milestones
DONOR_MILESTONES = {
    5: {"bonus": 150, "cert_title": "Bronze Appreciation Certificate", "badge_key": "donor_bronze"},
    10: {"bonus": 300, "cert_title": "Silver Appreciation Certificate", "badge_key": "donor_silver"},
    25: {"bonus": 500, "cert_title": "Gold Appreciation Certificate", "badge_key": "donor_gold"},
    50: {"bonus": 1000, "cert_title": "Platinum Appreciation Certificate", "badge_key": "donor_platinum"},
    100: {"bonus": 0, "cert_title": "Food Hero Certificate", "badge_key": "donor_food_hero"}
}

VOLUNTEER_MILESTONES = {
    5: {"bonus": 200, "cert_title": "Helping Hand Certificate", "badge_key": "vol_helping_hand"},
    10: {"bonus": 400, "cert_title": "Delivery Star Certificate", "badge_key": "vol_delivery_star"},
    25: {"bonus": 750, "cert_title": "Food Rescue Hero Certificate", "badge_key": "vol_rescue_hero"},
    50: {"bonus": 0, "cert_title": "Community Champion Certificate", "badge_key": "vol_community_champion"}
}

STREAK_MILESTONES = {
    2: {"bonus": 100},
    3: {"bonus": 200},
    6: {"bonus": 500},
    12: {"bonus": 0, "badge_key": "streak_consistency_champion"}
}


# ─── Schema Migration & Initialization ─────────────────────────────────────────

def init_rewards_schema(conn):
    """Creates rewards-related tables safely and seeds catalog and badges."""
    cur = conn.cursor()

    # 1. Reward Accounts Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reward_accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_role TEXT NOT NULL,
            current_balance INTEGER DEFAULT 0,
            lifetime_points INTEGER DEFAULT 0,
            current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0,
            last_donation_month TEXT,
            leaderboard_opt_in INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, user_role)
        )
    ''')

    # 2. Reward Transactions Ledger Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reward_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_role TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            points INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            description TEXT NOT NULL,
            reference_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, user_role, reference_id)
        )
    ''')

    # 3. Achievement Badges Definition Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS achievement_badges (
            badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            badge_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            threshold INTEGER NOT NULL,
            metric TEXT DEFAULT 'count',
            icon TEXT
        )
    ''')

    # 4. User Earned Achievements Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_role TEXT NOT NULL,
            badge_key TEXT NOT NULL,
            unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_revoked INTEGER DEFAULT 0,
            UNIQUE(user_id, user_role, badge_key)
        )
    ''')

    # 5. Reward Catalog Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reward_catalog (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            points_cost INTEGER NOT NULL,
            description TEXT NOT NULL,
            item_type TEXT NOT NULL
        )
    ''')

    # 6. Reward Redemptions History Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reward_redemptions (
            redemption_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_role TEXT NOT NULL,
            item_key TEXT NOT NULL,
            points_spent INTEGER NOT NULL,
            status TEXT DEFAULT 'completed',
            reward_details TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 7. Appreciation Certificates Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reward_certificates (
            certificate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            cert_code TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            user_role TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            cert_type TEXT NOT NULL,
            milestone_title TEXT NOT NULL,
            milestone_count INTEGER DEFAULT 0,
            issued_date TEXT NOT NULL,
            pdf_path TEXT,
            reference_key TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, user_role, reference_key)
        )
    ''')

    # 8. In-App Notifications Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reward_notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_role TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            event_type TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 9. NGO Distribution Confirmations Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ngo_distribution_confirmations (
            confirmation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ngo_id INTEGER NOT NULL,
            delivery_id INTEGER UNIQUE NOT NULL,
            donation_id INTEGER NOT NULL,
            meals_distributed INTEGER NOT NULL,
            beneficiary_group TEXT,
            notes TEXT,
            distributed_date TEXT NOT NULL,
            confirmed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(ngo_id) REFERENCES ngo(ngo_id),
            FOREIGN KEY(delivery_id) REFERENCES delivery(delivery_id)
        )
    ''')

    # Seed Badges
    for b in DONOR_BADGES:
        cur.execute('''
            INSERT OR IGNORE INTO achievement_badges (badge_key, name, description, category, threshold, metric, icon)
            VALUES (?, ?, ?, 'donor', ?, 'count', ?)
        ''', (b['key'], b['name'], b['description'], b['threshold'], b['icon']))

    for b in VOLUNTEER_BADGES:
        cur.execute('''
            INSERT OR IGNORE INTO achievement_badges (badge_key, name, description, category, threshold, metric, icon)
            VALUES (?, ?, ?, 'volunteer', ?, 'count', ?)
        ''', (b['key'], b['name'], b['description'], b['threshold'], b['icon']))

    for b in NGO_BADGES:
        cur.execute('''
            INSERT OR IGNORE INTO achievement_badges (badge_key, name, description, category, threshold, metric, icon)
            VALUES (?, ?, ?, 'ngo', ?, ?, ?)
        ''', (b['key'], b['name'], b['description'], b['threshold'], b['metric'], b['icon']))

    for b in STREAK_BADGES:
        cur.execute('''
            INSERT OR IGNORE INTO achievement_badges (badge_key, name, description, category, threshold, metric, icon)
            VALUES (?, ?, ?, 'streak', ?, 'months', ?)
        ''', (b['key'], b['name'], b['description'], b['threshold'], b['icon']))

    # Seed Special Badges for redemptions
    cur.execute('''
        INSERT OR IGNORE INTO achievement_badges (badge_key, name, description, category, threshold, metric, icon)
        VALUES ('badge_eco_supporter', 'Eco Supporter', 'Exclusive redeemed profile recognition badge', 'special', 0, 'special', 'ri-shield-check-fill')
    ''')
    cur.execute('''
        INSERT OR IGNORE INTO achievement_badges (badge_key, name, description, category, threshold, metric, icon)
        VALUES ('badge_community_hero', 'Community Hero', 'Elite redeemed community recognition award', 'special', 0, 'special', 'ri-vip-crown-line')
    ''')

    # Seed Catalog
    for item in REWARD_CATALOG_ITEMS:
        cur.execute('''
            INSERT OR IGNORE INTO reward_catalog (item_key, name, points_cost, description, item_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (item['key'], item['name'], item['points_cost'], item['description'], item['item_type']))

    conn.commit()


# ─── Account Helpers ───────────────────────────────────────────────────────────

def get_or_create_account(conn, user_id: int, user_role: str):
    """Retrieves or initializes a user's reward account."""
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM reward_accounts WHERE user_id=? AND user_role=?",
        (user_id, user_role)
    )
    row = cur.fetchone()
    if row:
        return dict(row)

    cur.execute('''
        INSERT INTO reward_accounts (user_id, user_role, current_balance, lifetime_points, current_streak, longest_streak, leaderboard_opt_in)
        VALUES (?, ?, 0, 0, 0, 0, 1)
    ''', (user_id, user_role))
    conn.commit()

    cur.execute("SELECT * FROM reward_accounts WHERE user_id=? AND user_role=?", (user_id, user_role))
    return dict(cur.fetchone())


def add_notification(conn, user_id: int, user_role: str, title: str, message: str, event_type: str):
    """Logs an in-app notification for the user."""
    cur = conn.cursor()
    # Check if identical notification already sent recently
    cur.execute('''
        SELECT notification_id FROM reward_notifications
        WHERE user_id=? AND user_role=? AND title=? AND message=?
    ''', (user_id, user_role, title, message))
    if cur.fetchone():
        return
    cur.execute('''
        INSERT INTO reward_notifications (user_id, user_role, title, message, event_type)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, user_role, title, message, event_type))
    conn.commit()


def _record_point_transaction(conn, user_id: int, user_role: str, tx_type: str, points: int, description: str, reference_id: str):
    """
    Atomically updates user account balance and appends an immutable transaction record.
    Returns (success, balance_after).
    """
    cur = conn.cursor()
    # Check duplicate reference
    if reference_id:
        cur.execute('''
            SELECT transaction_id FROM reward_transactions
            WHERE user_id=? AND user_role=? AND reference_id=?
        ''', (user_id, user_role, reference_id))
        if cur.fetchone():
            return False, 0

    acc = get_or_create_account(conn, user_id, user_role)
    new_balance = acc['current_balance'] + points
    if new_balance < 0 and tx_type == 'redemption':
        return False, acc['current_balance']

    new_lifetime = acc['lifetime_points'] + max(0, points)

    cur.execute('''
        UPDATE reward_accounts
        SET current_balance=?, lifetime_points=?, updated_at=CURRENT_TIMESTAMP
        WHERE user_id=? AND user_role=?
    ''', (new_balance, new_lifetime, user_id, user_role))

    cur.execute('''
        INSERT INTO reward_transactions (user_id, user_role, transaction_type, points, balance_after, description, reference_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, user_role, tx_type, points, new_balance, description, reference_id))

    return True, new_balance


# ─── Automatic Donor Rewards Processing ────────────────────────────────────────

def process_donation_completed(conn, donation_id: int):
    """
    Called when an NGO confirms successful receipt of food (donation marked 'Completed').
    Awards FB points, checks milestones, badges, streaks, and certificates.
    """
    cur = conn.cursor()
    cur.execute('''
        SELECT fd.donation_id, fd.donor_id, fd.donation_status, fd.date_of_donation, d.donor_name
        FROM food_donation fd
        JOIN donor d ON d.donor_id = fd.donor_id
        WHERE fd.donation_id = ?
    ''', (donation_id,))
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": "Donation not found"}

    if row['donation_status'] != 'Completed':
        return {"success": False, "error": "Donation is not completed"}

    donor_id = row['donor_id']
    donor_name = row['donor_name']
    activity_ref = f"donation_{donation_id}"

    # Verify no duplicate points for this donation
    cur.execute('''
        SELECT transaction_id FROM reward_transactions
        WHERE user_id=? AND user_role='donor' AND reference_id=?
    ''', (donor_id, activity_ref))
    if cur.fetchone():
        return {"success": True, "already_processed": True}

    # Count total completed donations by this donor
    cur.execute('''
        SELECT COUNT(DISTINCT donation_id) FROM food_donation
        WHERE donor_id=? AND donation_status='Completed'
    ''', (donor_id,))
    total_completed = cur.fetchone()[0]

    # Rule 11: First donation gets +100 (replaces normal 50). Subsequent gets +50.
    if total_completed == 1:
        points = 100
        desc = "First Successful Food Donation (+100 FB Points)"
        tx_type = "donation_first"
    else:
        points = 50
        desc = f"Successful Food Donation #{total_completed} (+50 FB Points)"
        tx_type = "donation_subsequent"

    ok, balance = _record_point_transaction(conn, donor_id, 'donor', tx_type, points, desc, activity_ref)
    if not ok:
        return {"success": True, "already_processed": True}

    add_notification(conn, donor_id, 'donor',
                     "Points Earned!",
                     f"Congratulations! You earned {points} FB Points for your successful donation.",
                     "points")

    # Check Badges
    for b in DONOR_BADGES:
        if total_completed >= b['threshold']:
            cur.execute('''
                INSERT OR IGNORE INTO user_achievements (user_id, user_role, badge_key)
                VALUES (?, 'donor', ?)
            ''', (donor_id, b['key']))
            if cur.rowcount > 0:
                add_notification(conn, donor_id, 'donor',
                                 "Badge Unlocked!",
                                 f"You unlocked the {b['name']} badge!",
                                 "badge")

    # Check Milestone Bonuses & Milestone Appreciation Certificates
    if total_completed in DONOR_MILESTONES:
        ms = DONOR_MILESTONES[total_completed]
        bonus = ms['bonus']
        if bonus > 0:
            ms_ref = f"milestone_donor_{donor_id}_{total_completed}"
            ms_ok, _ = _record_point_transaction(
                conn, donor_id, 'donor', f"milestone_{total_completed}",
                bonus, f"Donation Milestone Bonus ({total_completed} Donations: +{bonus} Points)",
                ms_ref
            )
            if ms_ok:
                add_notification(conn, donor_id, 'donor',
                                 "Milestone Bonus!",
                                 f"Milestone reached: {total_completed} donations! You earned +{bonus} bonus FB points.",
                                 "milestone")

        # Automatic Certificate Generation
        cert_title = ms['cert_title']
        cert_ref = f"milestone_donor_{total_completed}"
        generate_milestone_certificate(conn, donor_id, 'donor', donor_name, cert_title, total_completed, cert_ref)

    # Monthly Donation Streak Calculation
    _update_donor_streak(conn, donor_id, row['date_of_donation'])

    conn.commit()
    return {"success": True, "points_awarded": points, "total_completed": total_completed}


def _update_donor_streak(conn, donor_id: int, donation_date_str: str):
    """
    Updates the monthly contribution streak for a donor.
    Streak increases when completed donation occurs in consecutive calendar months.
    """
    cur = conn.cursor()
    # Parse month from donation date or default to current month
    try:
        don_date = datetime.strptime(donation_date_str, '%Y-%m-%d').date() if donation_date_str else date.today()
    except Exception:
        don_date = date.today()

    don_month = don_date.strftime('%Y-%m')  # e.g., '2026-10'

    acc = get_or_create_account(conn, donor_id, 'donor')

    last_month = acc.get('last_donation_month')
    current_streak = acc.get('current_streak', 0)
    longest_streak = acc.get('longest_streak', 0)

    if last_month == don_month:
        # Same month: multiple donations do not increase streak more than once
        return

    is_consecutive = False
    if last_month:
        try:
            last_dt = datetime.strptime(last_month, '%Y-%m').date()
            # Check if don_date month is exactly next calendar month
            expected_year = last_dt.year + (1 if last_dt.month == 12 else 0)
            expected_month = 1 if last_dt.month == 12 else last_dt.month + 1
            if don_date.year == expected_year and don_date.month == expected_month:
                is_consecutive = True
        except Exception:
            is_consecutive = False

    if is_consecutive:
        current_streak += 1
    else:
        current_streak = 1

    longest_streak = max(longest_streak, current_streak)

    cur.execute('''
        UPDATE reward_accounts
        SET current_streak=?, longest_streak=?, last_donation_month=?, updated_at=CURRENT_TIMESTAMP
        WHERE user_id=? AND user_role='donor'
    ''', (current_streak, longest_streak, don_month, donor_id))

    # Streak Milestone Rewards
    if current_streak in STREAK_MILESTONES:
        s_info = STREAK_MILESTONES[current_streak]
        s_bonus = s_info.get('bonus', 0)
        s_badge = s_info.get('badge_key')
        s_ref = f"streak_donor_{donor_id}_{current_streak}_{don_month}"

        if s_bonus > 0:
            s_ok, _ = _record_point_transaction(
                conn, donor_id, 'donor', 'streak_bonus',
                s_bonus, f"{current_streak}-Month Donation Streak Bonus (+{s_bonus} FB Points)",
                s_ref
            )
            if s_ok:
                add_notification(conn, donor_id, 'donor',
                                 "Streak Bonus!",
                                 f"Congratulations! You completed a {current_streak}-month donation streak and earned +{s_bonus} Points.",
                                 "streak")

        if s_badge:
            cur.execute('''
                INSERT OR IGNORE INTO user_achievements (user_id, user_role, badge_key)
                VALUES (?, 'donor', ?)
            ''', (donor_id, s_badge))
            if cur.rowcount > 0:
                add_notification(conn, donor_id, 'donor',
                                 "Badge Unlocked!",
                                 "You unlocked the Consistency Champion badge for 12 months streak!",
                                 "badge")


# ─── Automatic Volunteer Rewards Processing ────────────────────────────────────

def process_delivery_completed(conn, pickup_id: int):
    """
    Called when a delivery is verified complete (OTP verified or NGO confirmed receipt).
    Awards FB points, checks milestones, badges, and certificates for the volunteer.
    """
    cur = conn.cursor()
    cur.execute('''
        SELECT p.pickup_id, p.volunteer_id, p.status, v.name AS volunteer_name, dl.delivery_id
        FROM pickup p
        JOIN volunteer v ON v.volunteer_id = p.volunteer_id
        LEFT JOIN delivery dl ON dl.pickup_id = p.pickup_id
        WHERE p.pickup_id = ?
    ''', (pickup_id,))
    row = cur.fetchone()
    if not row or not row['volunteer_id']:
        return {"success": False, "error": "Pickup or volunteer not found"}

    if row['status'] != 'Delivered':
        return {"success": False, "error": "Pickup is not delivered"}

    vol_id = row['volunteer_id']
    vol_name = row['volunteer_name']
    activity_ref = f"pickup_{pickup_id}"

    # Verify no duplicate points
    cur.execute('''
        SELECT transaction_id FROM reward_transactions
        WHERE user_id=? AND user_role='volunteer' AND reference_id=?
    ''', (vol_id, activity_ref))
    if cur.fetchone():
        return {"success": True, "already_processed": True}

    # Count total completed deliveries by this volunteer
    cur.execute('''
        SELECT COUNT(DISTINCT pickup_id) FROM pickup
        WHERE volunteer_id=? AND status='Delivered'
    ''', (vol_id,))
    total_completed = cur.fetchone()[0]

    # Rule 11: First delivery gets +100 (replaces normal 75). Subsequent gets +75.
    if total_completed == 1:
        points = 100
        desc = "First Successful Delivery (+100 FB Points)"
        tx_type = "volunteer_first"
    else:
        points = 75
        desc = f"Successful Food Delivery #{total_completed} (+75 FB Points)"
        tx_type = "volunteer_subsequent"

    ok, balance = _record_point_transaction(conn, vol_id, 'volunteer', tx_type, points, desc, activity_ref)
    if not ok:
        return {"success": True, "already_processed": True}

    add_notification(conn, vol_id, 'volunteer',
                     "Points Earned!",
                     f"Congratulations! You earned {points} FB Points for your completed delivery.",
                     "points")

    # Check Badges
    for b in VOLUNTEER_BADGES:
        if total_completed >= b['threshold']:
            cur.execute('''
                INSERT OR IGNORE INTO user_achievements (user_id, user_role, badge_key)
                VALUES (?, 'volunteer', ?)
            ''', (vol_id, b['key']))
            if cur.rowcount > 0:
                add_notification(conn, vol_id, 'volunteer',
                                 "Badge Unlocked!",
                                 f"You unlocked the {b['name']} badge!",
                                 "badge")

    # Check Milestones & Certificates
    if total_completed in VOLUNTEER_MILESTONES:
        ms = VOLUNTEER_MILESTONES[total_completed]
        bonus = ms['bonus']
        if bonus > 0:
            ms_ref = f"milestone_vol_{vol_id}_{total_completed}"
            ms_ok, _ = _record_point_transaction(
                conn, vol_id, 'volunteer', f"milestone_{total_completed}",
                bonus, f"Delivery Milestone Bonus ({total_completed} Deliveries: +{bonus} Points)",
                ms_ref
            )
            if ms_ok:
                add_notification(conn, vol_id, 'volunteer',
                                 "Milestone Bonus!",
                                 f"Milestone reached: {total_completed} deliveries! You earned +{bonus} bonus FB points.",
                                 "milestone")

        cert_title = ms['cert_title']
        cert_ref = f"milestone_vol_{total_completed}"
        generate_milestone_certificate(conn, vol_id, 'volunteer', vol_name, cert_title, total_completed, cert_ref)

    conn.commit()
    return {"success": True, "points_awarded": points, "total_completed": total_completed}


# ─── Certificate Generation (ReportLab) ────────────────────────────────────────

def generate_milestone_certificate(conn, user_id: int, user_role: str, recipient_name: str,
                                   milestone_title: str, milestone_count: int, reference_key: str):
    """Generates an official appreciation certificate record and writes PDF."""
    cur = conn.cursor()
    # Check if already generated
    cur.execute('''
        SELECT certificate_id, cert_code FROM reward_certificates
        WHERE user_id=? AND user_role=? AND reference_key=?
    ''', (user_id, user_role, reference_key))
    existing = cur.fetchone()
    if existing:
        return existing['cert_code']

    role_code = "DONOR" if user_role == 'donor' else "VOL"
    cert_code = f"FB-{role_code}-{milestone_count:05d}-{uuid.uuid4().hex[:6].upper()}"
    today_str = date.today().strftime('%d %B %Y')

    pdf_filename = f"{cert_code}.pdf"
    pdf_path = os.path.join(CERTIFICATES_DIR, pdf_filename)

    cert_data = {
        "cert_code": cert_code,
        "recipient_name": recipient_name,
        "milestone_title": milestone_title,
        "milestone_count": milestone_count,
        "role_label": "Food Donations" if user_role == 'donor' else "Food Deliveries",
        "issued_date": today_str,
        "cert_type": "Milestone Achievement"
    }

    _build_pdf_certificate(pdf_path, cert_data)

    cur.execute('''
        INSERT INTO reward_certificates (cert_code, user_id, user_role, recipient_name, cert_type, milestone_title, milestone_count, issued_date, pdf_path, reference_key)
        VALUES (?, ?, ?, ?, 'milestone', ?, ?, ?, ?, ?)
    ''', (cert_code, user_id, user_role, recipient_name, milestone_title, milestone_count, today_str, pdf_filename, reference_key))

    add_notification(conn, user_id, user_role,
                     "Certificate Earned!",
                     f"You earned a new appreciation certificate: {milestone_title}!",
                     "certificate")

    return cert_code


def generate_redeemed_certificate(conn, user_id: int, user_role: str, recipient_name: str,
                                  cert_name: str, redemption_id: int):
    """Generates a points-based redeemed appreciation certificate."""
    cur = conn.cursor()
    cert_code = f"FB-REDEEM-{redemption_id:05d}-{uuid.uuid4().hex[:6].upper()}"
    today_str = date.today().strftime('%d %B %Y')
    pdf_filename = f"{cert_code}.pdf"
    pdf_path = os.path.join(CERTIFICATES_DIR, pdf_filename)

    cert_data = {
        "cert_code": cert_code,
        "recipient_name": recipient_name,
        "milestone_title": cert_name,
        "milestone_count": 0,
        "role_label": "Points-Based Recognition Reward",
        "issued_date": today_str,
        "cert_type": "Redeemed Recognition Reward"
    }

    _build_pdf_certificate(pdf_path, cert_data)

    ref_key = f"redemption_cert_{redemption_id}"
    cur.execute('''
        INSERT INTO reward_certificates (cert_code, user_id, user_role, recipient_name, cert_type, milestone_title, milestone_count, issued_date, pdf_path, reference_key)
        VALUES (?, ?, ?, ?, 'redemption', ?, 0, ?, ?, ?)
    ''', (cert_code, user_id, user_role, recipient_name, cert_name, today_str, pdf_filename, ref_key))

    return cert_code


def _build_pdf_certificate(output_path: str, data: dict):
    """Builds an elegant landscape Certificate of Appreciation using ReportLab."""
    c = canvas.Canvas(output_path, pagesize=landscape(letter))
    width, height = landscape(letter)  # 792 x 612 pt

    # Outer decorative background & border
    c.setStrokeColor(colors.HexColor('#1e293b'))
    c.setLineWidth(4)
    c.rect(20, 20, width - 40, height - 40)

    # Inner Gold / Emerald accent border
    c.setStrokeColor(colors.HexColor('#10b981'))
    c.setLineWidth(1.5)
    c.rect(26, 26, width - 52, height - 52)

    # Thin corner decorative marks
    c.setStrokeColor(colors.HexColor('#f59e0b'))
    c.setLineWidth(2)
    c.line(32, 42, 62, 42)
    c.line(42, 32, 42, 62)
    c.line(width - 32, 42, width - 62, 42)
    c.line(width - 42, 32, width - 42, 62)
    c.line(32, height - 42, 62, height - 42)
    c.line(42, height - 32, 42, height - 62)
    c.line(width - 32, height - 42, width - 62, height - 42)
    c.line(width - 42, height - 32, width - 42, height - 62)

    # Header branding
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor('#10b981'))
    c.drawCentredString(width / 2.0, height - 70, "FOODBRIDGE PLATFORM")

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor('#64748b'))
    c.drawCentredString(width / 2.0, height - 85, "ZERO SURPLUS FOOD WASTE NETWORK")

    # Certificate Heading
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(colors.HexColor('#0f172a'))
    c.drawCentredString(width / 2.0, height - 130, "CERTIFICATE OF APPRECIATION")

    # Divider bar
    c.setStrokeColor(colors.HexColor('#f59e0b'))
    c.setLineWidth(2)
    c.line(width / 2.0 - 100, height - 145, width / 2.0 + 100, height - 145)

    # Presentation text
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor('#475569'))
    c.drawCentredString(width / 2.0, height - 180, "This certificate is proudly presented to")

    # Recipient Name
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(colors.HexColor('#065f46'))
    c.drawCentredString(width / 2.0, height - 220, data.get('recipient_name', 'Honored Contributor').upper())

    # Achievement details
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor('#334155'))
    count = data.get('milestone_count', 0)
    if count > 0:
        c.drawCentredString(width / 2.0, height - 260, f"For successfully completing {count} {data.get('role_label', 'Contributions')}")
    else:
        c.drawCentredString(width / 2.0, height - 260, f"In recognition of distinguished dedication as a {data.get('role_label')}")

    c.setFont("Helvetica", 11)
    c.setFillColor(colors.HexColor('#64748b'))
    c.drawCentredString(width / 2.0, height - 290, "In recognition of exceptional contribution towards reducing food waste,")
    c.drawCentredString(width / 2.0, height - 305, "supporting local communities, and bridging surplus nutrition to hungry hearts.")

    # Achievement Badge / Title banner
    title = data.get('milestone_title', 'Appreciation Award').upper()
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(colors.HexColor('#d97706'))
    c.drawCentredString(width / 2.0, height - 355, f"★  {title}  ★")

    # Type label
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor('#059669'))
    c.drawCentredString(width / 2.0, height - 375, f"[{data.get('cert_type', 'Official Recognition')}]")

    # Bottom Metadata
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor('#1e293b'))
    c.drawString(60, 95, f"Date: {data.get('issued_date', '')}")
    c.drawString(60, 78, f"Certificate ID: {data.get('cert_code', '')}")

    c.drawRightString(width - 60, 95, "FoodBridge Automated Recognition System")
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor('#64748b'))
    c.drawRightString(width - 60, 78, "Cryptographically Verified Digital Record • Official Issue")

    c.save()


# ─── Leaderboard Engine ────────────────────────────────────────────────────────

def get_leaderboard(conn, role: str, leaderboard_type: str = 'monthly'):
    """
    Returns rankings for Top Donors or Top Volunteers.
    Filters: leaderboard_opt_in = 1.
    Never exposes phone numbers, addresses, or documents.
    """
    cur = conn.cursor()
    current_month_str = date.today().strftime('%Y-%m')

    if role == 'donor':
        if leaderboard_type == 'monthly':
            # Calculate points and completed donations in current calendar month
            query = """
                SELECT d.donor_id AS user_id,
                       d.donor_name AS display_name,
                       COALESCE(m_stats.m_count, 0) AS contributions,
                       COALESCE(m_pts.m_points, 0) AS points
                FROM donor d
                LEFT JOIN reward_accounts ra ON ra.user_id = d.donor_id AND ra.user_role = 'donor'
                LEFT JOIN (
                    SELECT donor_id, COUNT(*) AS m_count
                    FROM food_donation
                    WHERE donation_status = 'Completed'
                      AND (date_of_donation LIKE ? || '%' OR strftime('%Y-%m', date_of_donation) = ?)
                    GROUP BY donor_id
                ) m_stats ON m_stats.donor_id = d.donor_id
                LEFT JOIN (
                    SELECT user_id, SUM(points) AS m_points
                    FROM reward_transactions
                    WHERE user_role = 'donor' AND points > 0
                      AND strftime('%Y-%m', created_at) = ?
                    GROUP BY user_id
                ) m_pts ON m_pts.user_id = d.donor_id
                WHERE COALESCE(ra.leaderboard_opt_in, 1) = 1
                ORDER BY points DESC, contributions DESC, d.donor_id ASC
                LIMIT 100
            """
            cur.execute(query, (current_month_str, current_month_str, current_month_str))
        else:
            # All-time leaderboard
            query = """
                SELECT d.donor_id AS user_id,
                       d.donor_name AS display_name,
                       COALESCE(c_stats.total_count, 0) AS contributions,
                       COALESCE(ra.lifetime_points, 0) AS points
                FROM donor d
                LEFT JOIN reward_accounts ra ON ra.user_id = d.donor_id AND ra.user_role = 'donor'
                LEFT JOIN (
                    SELECT donor_id, COUNT(*) AS total_count
                    FROM food_donation
                    WHERE donation_status = 'Completed'
                    GROUP BY donor_id
                ) c_stats ON c_stats.donor_id = d.donor_id
                WHERE COALESCE(ra.leaderboard_opt_in, 1) = 1
                ORDER BY points DESC, contributions DESC, d.donor_id ASC
                LIMIT 100
            """
            cur.execute(query)
    else:
        # Volunteer Leaderboard
        if leaderboard_type == 'monthly':
            query = """
                SELECT v.volunteer_id AS user_id,
                       v.name AS display_name,
                       COALESCE(m_stats.m_count, 0) AS contributions,
                       COALESCE(m_pts.m_points, 0) AS points
                FROM volunteer v
                LEFT JOIN reward_accounts ra ON ra.user_id = v.volunteer_id AND ra.user_role = 'volunteer'
                LEFT JOIN (
                    SELECT volunteer_id, COUNT(*) AS m_count
                    FROM pickup
                    WHERE status = 'Delivered'
                      AND strftime('%Y-%m', time) = ?
                    GROUP BY volunteer_id
                ) m_stats ON m_stats.volunteer_id = v.volunteer_id
                LEFT JOIN (
                    SELECT user_id, SUM(points) AS m_points
                    FROM reward_transactions
                    WHERE user_role = 'volunteer' AND points > 0
                      AND strftime('%Y-%m', created_at) = ?
                    GROUP BY user_id
                ) m_pts ON m_pts.user_id = v.volunteer_id
                WHERE COALESCE(ra.leaderboard_opt_in, 1) = 1
                ORDER BY points DESC, contributions DESC, v.volunteer_id ASC
                LIMIT 100
            """
            cur.execute(query, (current_month_str, current_month_str))
        else:
            query = """
                SELECT v.volunteer_id AS user_id,
                       v.name AS display_name,
                       COALESCE(c_stats.total_count, 0) AS contributions,
                       COALESCE(ra.lifetime_points, 0) AS points
                FROM volunteer v
                LEFT JOIN reward_accounts ra ON ra.user_id = v.volunteer_id AND ra.user_role = 'volunteer'
                LEFT JOIN (
                    SELECT volunteer_id, COUNT(*) AS total_count
                    FROM pickup
                    WHERE status = 'Delivered'
                    GROUP BY volunteer_id
                ) c_stats ON c_stats.volunteer_id = v.volunteer_id
                WHERE COALESCE(ra.leaderboard_opt_in, 1) = 1
                ORDER BY points DESC, contributions DESC, v.volunteer_id ASC
                LIMIT 100
            """
            cur.execute(query)

    rows = cur.fetchall()
    leaderboard = []
    for rank, r in enumerate(rows, start=1):
        # Determine highest badge for display
        badge_name = _get_highest_badge(conn, r['user_id'], role)
        leaderboard.append({
            "rank": rank,
            "display_name": r['display_name'],
            "contributions": r['contributions'],
            "points": r['points'],
            "badge": badge_name
        })

    return leaderboard


def _get_highest_badge(conn, user_id: int, role: str) -> str:
    """Returns the name of the highest tier badge unlocked by the user."""
    cur = conn.cursor()
    cur.execute('''
        SELECT ab.name, ab.threshold
        FROM user_achievements ua
        JOIN achievement_badges ab ON ab.badge_key = ua.badge_key
        WHERE ua.user_id=? AND ua.user_role=? AND ua.is_revoked=0
        ORDER BY ab.threshold DESC
        LIMIT 1
    ''', (user_id, role))
    row = cur.fetchone()
    if row:
        return row['name']
    return "New Contributor"


# ─── Personal Impact & Profile Details ─────────────────────────────────────────

def get_donor_impact_summary(conn, donor_id: int):
    """Calculates real metrics for the Donor Personal Impact Dashboard."""
    cur = conn.cursor()
    acc = get_or_create_account(conn, donor_id, 'donor')

    # Completed donations count & total food quantity
    cur.execute('''
        SELECT COUNT(*) AS total_donations,
               COALESCE(SUM(quantity), 0) AS total_qty
        FROM food_donation
        WHERE donor_id=? AND donation_status='Completed'
    ''', (donor_id,))
    comp_row = cur.fetchone()
    total_donations = comp_row['total_donations'] if comp_row else 0
    total_qty = comp_row['total_qty'] if comp_row else 0

    # Meal estimation: 1 quantity = 1 meal (serving), or 2.5 meals if measured in kg
    # Since food_donation quantity tracks servings / meals, 1:1 estimate
    estimated_meals = int(total_qty)

    # Next badge determination
    next_badge = None
    progress_str = "Completed"
    for b in DONOR_BADGES:
        if total_donations < b['threshold']:
            next_badge = b['name']
            progress_str = f"{total_donations}/{b['threshold']} Donations"
            break

    current_badge = _get_highest_badge(conn, donor_id, 'donor')

    # Earned badges
    cur.execute('''
        SELECT ab.badge_key, ab.name, ab.description, ab.icon, ua.unlocked_at
        FROM user_achievements ua
        JOIN achievement_badges ab ON ab.badge_key = ua.badge_key
        WHERE ua.user_id=? AND ua.user_role='donor' AND ua.is_revoked=0
        ORDER BY ab.threshold ASC
    ''', (donor_id,))
    badges_earned = [dict(r) for r in cur.fetchall()]

    # Locked badges
    earned_keys = {b['badge_key'] for b in badges_earned}
    badges_locked = []
    for b in DONOR_BADGES:
        if b['key'] not in earned_keys:
            badges_locked.append({
                "badge_key": b['key'],
                "name": b['name'],
                "description": b['description'],
                "threshold": b['threshold'],
                "progress": f"{min(total_donations, b['threshold'])}/{b['threshold']}"
            })

    # Certificates count
    cur.execute("SELECT COUNT(*) FROM reward_certificates WHERE user_id=? AND user_role='donor'", (donor_id,))
    cert_count = cur.fetchone()[0]

    return {
        "total_successful_donations": total_donations,
        "total_quantity_donated": f"{total_qty} Units",
        "estimated_meals_provided": estimated_meals,
        "conversion_note": "Estimated at 1 meal per portion / 2.5 meals per kg",
        "lifetime_points": acc['lifetime_points'],
        "available_points": acc['current_balance'],
        "current_badge": current_badge,
        "next_badge": next_badge or "Max Tier Reached",
        "badge_progress": progress_str,
        "current_streak": acc['current_streak'],
        "longest_streak": acc['longest_streak'],
        "certificates_earned_count": cert_count,
        "leaderboard_opt_in": bool(acc['leaderboard_opt_in']),
        "badges_earned": badges_earned,
        "badges_locked": badges_locked
    }


def get_volunteer_impact_summary(conn, volunteer_id: int):
    """Calculates real metrics for the Volunteer Personal Impact Dashboard."""
    cur = conn.cursor()
    acc = get_or_create_account(conn, volunteer_id, 'volunteer')

    # Completed deliveries count & quantity transported
    cur.execute('''
        SELECT COUNT(DISTINCT p.pickup_id) AS total_deliveries,
               COALESCE(SUM(fd.quantity), 0) AS total_food_transported
        FROM pickup p
        JOIN food_donation fd ON fd.donation_id = p.donation_id
        WHERE p.volunteer_id=? AND p.status='Delivered'
    ''', (volunteer_id,))
    row = cur.fetchone()
    total_deliveries = row['total_deliveries'] if row else 0
    total_food = row['total_food_transported'] if row else 0
    estimated_meals = int(total_food)

    next_badge = None
    progress_str = "Completed"
    for b in VOLUNTEER_BADGES:
        if total_deliveries < b['threshold']:
            next_badge = b['name']
            progress_str = f"{total_deliveries}/{b['threshold']} Deliveries"
            break

    current_badge = _get_highest_badge(conn, volunteer_id, 'volunteer')

    # Earned badges
    cur.execute('''
        SELECT ab.badge_key, ab.name, ab.description, ab.icon, ua.unlocked_at
        FROM user_achievements ua
        JOIN achievement_badges ab ON ab.badge_key = ua.badge_key
        WHERE ua.user_id=? AND ua.user_role='volunteer' AND ua.is_revoked=0
        ORDER BY ab.threshold ASC
    ''', (volunteer_id,))
    badges_earned = [dict(r) for r in cur.fetchall()]

    earned_keys = {b['badge_key'] for b in badges_earned}
    badges_locked = []
    for b in VOLUNTEER_BADGES:
        if b['key'] not in earned_keys:
            badges_locked.append({
                "badge_key": b['key'],
                "name": b['name'],
                "description": b['description'],
                "threshold": b['threshold'],
                "progress": f"{min(total_deliveries, b['threshold'])}/{b['threshold']}"
            })

    cur.execute("SELECT COUNT(*) FROM reward_certificates WHERE user_id=? AND user_role='volunteer'", (volunteer_id,))
    cert_count = cur.fetchone()[0]

    return {
        "total_completed_deliveries": total_deliveries,
        "total_food_transported": f"{total_food} Units",
        "estimated_meals_delivered": estimated_meals,
        "conversion_note": "Estimated at 1 meal per portion / 2.5 meals per kg",
        "lifetime_points": acc['lifetime_points'],
        "available_points": acc['current_balance'],
        "current_badge": current_badge,
        "next_badge": next_badge or "Max Tier Reached",
        "badge_progress": progress_str,
        "certificates_earned_count": cert_count,
        "leaderboard_opt_in": bool(acc['leaderboard_opt_in']),
        "badges_earned": badges_earned,
        "badges_locked": badges_locked
    }


# ─── NGO Impact Recognition & Distribution Confirmation ───────────────────────

def get_ngo_impact_summary(conn, ngo_id: int):
    """Calculates metrics for the NGO Impact Recognition Dashboard."""
    cur = conn.cursor()

    # Total donations received
    cur.execute('''
        SELECT COUNT(DISTINCT dl.delivery_id) AS total_received,
               COALESCE(SUM(fd.quantity), 0) AS total_food_received
        FROM delivery dl
        JOIN pickup p ON p.pickup_id = dl.pickup_id
        JOIN food_donation fd ON fd.donation_id = p.donation_id
        WHERE dl.ngo_id=? AND dl.delivery_status='Delivered'
    ''', (ngo_id,))
    rec_row = cur.fetchone()
    total_received = rec_row['total_received'] if rec_row else 0
    total_food_rec = rec_row['total_food_received'] if rec_row else 0

    # Total verified distributions & meals distributed
    cur.execute('''
        SELECT COUNT(*) AS total_distributions,
               COALESCE(SUM(meals_distributed), 0) AS total_meals_dist
        FROM ngo_distribution_confirmations
        WHERE ngo_id=?
    ''', (ngo_id,))
    dist_row = cur.fetchone()
    total_distributions = dist_row['total_distributions'] if dist_row else 0
    total_meals_dist = dist_row['total_meals_dist'] if dist_row else 0

    # Check and unlock NGO badges automatically
    for b in NGO_BADGES:
        eligible = False
        if b['metric'] == 'meals' and total_meals_dist >= b['threshold']:
            eligible = True
        elif b['metric'] == 'distributions' and total_distributions >= b['threshold']:
            eligible = True

        if eligible:
            cur.execute('''
                INSERT OR IGNORE INTO user_achievements (user_id, user_role, badge_key)
                VALUES (?, 'ngo', ?)
            ''', (ngo_id, b['key']))
            if cur.rowcount > 0:
                add_notification(conn, ngo_id, 'ngo',
                                 "NGO Badge Unlocked!",
                                 f"Congratulations! Your NGO unlocked the {b['name']} impact badge!",
                                 "badge")

    current_badge = _get_highest_badge(conn, ngo_id, 'ngo')

    # Get earned & locked badges for NGO
    cur.execute('''
        SELECT ab.badge_key, ab.name, ab.description, ab.icon, ua.unlocked_at
        FROM user_achievements ua
        JOIN achievement_badges ab ON ab.badge_key = ua.badge_key
        WHERE ua.user_id=? AND ua.user_role='ngo' AND ua.is_revoked=0
    ''', (ngo_id,))
    badges_earned = [dict(r) for r in cur.fetchall()]
    earned_keys = {b['badge_key'] for b in badges_earned}

    badges_locked = []
    for b in NGO_BADGES:
        if b['key'] not in earned_keys:
            val = total_meals_dist if b['metric'] == 'meals' else total_distributions
            unit = "meals" if b['metric'] == 'meals' else "distributions"
            badges_locked.append({
                "badge_key": b['key'],
                "name": b['name'],
                "description": b['description'],
                "threshold": b['threshold'],
                "progress": f"{min(val, b['threshold'])}/{b['threshold']} {unit}"
            })

    # Deliveries eligible for distribution confirmation (Delivered but not yet confirmed)
    cur.execute('''
        SELECT dl.delivery_id, dl.time, fd.donation_id, fd.food_type, fd.quantity, d.donor_name
        FROM delivery dl
        JOIN pickup p ON p.pickup_id = dl.pickup_id
        JOIN food_donation fd ON fd.donation_id = p.donation_id
        JOIN donor d ON d.donor_id = fd.donor_id
        LEFT JOIN ngo_distribution_confirmations ndc ON ndc.delivery_id = dl.delivery_id
        WHERE dl.ngo_id=? AND dl.delivery_status='Delivered' AND ndc.confirmation_id IS NULL
        ORDER BY dl.delivery_id DESC
    ''', (ngo_id,))
    pending_confirmations = [dict(r) for r in cur.fetchall()]

    # Past distribution confirmations
    cur.execute('''
        SELECT ndc.*, fd.food_type
        FROM ngo_distribution_confirmations ndc
        JOIN food_donation fd ON fd.donation_id = ndc.donation_id
        WHERE ndc.ngo_id=?
        ORDER BY ndc.confirmation_id DESC
    ''', (ngo_id,))
    confirmed_history = [dict(r) for r in cur.fetchall()]

    return {
        "total_donations_received": total_received,
        "total_food_received": f"{total_food_rec} Units",
        "total_verified_distributions": total_distributions,
        "estimated_meals_distributed": total_meals_dist,
        "current_badge": current_badge,
        "badges_earned": badges_earned,
        "badges_locked": badges_locked,
        "pending_confirmations": pending_confirmations,
        "confirmed_history": confirmed_history
    }


def confirm_ngo_distribution(conn, ngo_id: int, delivery_id: int, meals_distributed: int,
                             beneficiary_group: str, notes: str, distributed_date: str):
    """
    Records an authentic food distribution confirmation by an NGO.
    Validates delivery belongs to the NGO and prevents duplicates.
    """
    cur = conn.cursor()
    cur.execute('''
        SELECT dl.delivery_id, dl.ngo_id, dl.delivery_status, p.donation_id
        FROM delivery dl
        JOIN pickup p ON p.pickup_id = dl.pickup_id
        WHERE dl.delivery_id=? AND dl.ngo_id=?
    ''', (delivery_id, ngo_id))
    dl = cur.fetchone()
    if not dl:
        return {"success": False, "error": "Delivery record not found or unauthorized"}
    if dl['delivery_status'] != 'Delivered':
        return {"success": False, "error": "Food has not yet been marked as received"}

    # Check duplicate confirmation
    cur.execute("SELECT confirmation_id FROM ngo_distribution_confirmations WHERE delivery_id=?", (delivery_id,))
    if cur.fetchone():
        return {"success": False, "error": "Distribution already confirmed for this delivery"}

    if not distributed_date:
        distributed_date = date.today().strftime('%Y-%m-%d')

    cur.execute('''
        INSERT INTO ngo_distribution_confirmations (ngo_id, delivery_id, donation_id, meals_distributed, beneficiary_group, notes, distributed_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (ngo_id, delivery_id, dl['donation_id'], meals_distributed, beneficiary_group or 'Local Community', notes or '', distributed_date))
    conn.commit()

    # Re-evaluate NGO badges
    get_ngo_impact_summary(conn, ngo_id)
    return {"success": True, "message": "Distribution confirmed successfully!"}


# ─── Rewards Redemption Store ──────────────────────────────────────────────────

def redeem_reward(conn, user_id: int, user_role: str, item_key: str, recipient_name: str = None):
    """
    Redeems an item from the digital recognition catalog.
    Deducts points, records transaction and redemptions atomically.
    """
    cur = conn.cursor()
    cur.execute("SELECT * FROM reward_catalog WHERE item_key=?", (item_key,))
    item = cur.fetchone()
    if not item:
        return {"success": False, "error": "Catalog item not found"}

    item_cost = item['points_cost']
    item_name = item['name']
    item_type = item['item_type']

    acc = get_or_create_account(conn, user_id, user_role)
    if acc['current_balance'] < item_cost:
        return {
            "success": False,
            "error": f"Insufficient FoodBridge Points. You have {acc['current_balance']} FB Points, but {item_cost} FB Points are required."
        }

    # Atomic deduction
    ref_uuid = uuid.uuid4().hex[:8]
    ref_id = f"redemption_{item_key}_{ref_uuid}"
    desc = f"Redeemed: {item_name} (-{item_cost} FB Points)"

    ok, balance = _record_point_transaction(conn, user_id, user_role, "redemption", -item_cost, desc, ref_id)
    if not ok:
        return {"success": False, "error": "Transaction could not be completed"}

    # Insert redemption record
    cur.execute('''
        INSERT INTO reward_redemptions (user_id, user_role, item_key, points_spent, status, reward_details)
        VALUES (?, ?, ?, ?, 'completed', ?)
    ''', (user_id, user_role, item_key, item_cost, f"Unlocked {item_name}"))
    redemption_id = cur.lastrowid

    # Unlock corresponding digital item
    reward_result = {}
    if item_type in ('certificate_bronze', 'certificate_gold'):
        name = recipient_name or f"{user_role.capitalize()} #{user_id}"
        cert_code = generate_redeemed_certificate(conn, user_id, user_role, name, item_name, redemption_id)
        reward_result['certificate_code'] = cert_code
    elif item_type == 'profile_badge':
        cur.execute('''
            INSERT OR IGNORE INTO user_achievements (user_id, user_role, badge_key)
            VALUES (?, ?, 'badge_eco_supporter')
        ''', (user_id, user_role))
        reward_result['badge'] = "Eco Supporter"
    elif item_type == 'community_hero':
        cur.execute('''
            INSERT OR IGNORE INTO user_achievements (user_id, user_role, badge_key)
            VALUES (?, ?, 'badge_community_hero')
        ''', (user_id, user_role))
        reward_result['badge'] = "Community Hero"

    add_notification(conn, user_id, user_role,
                     "Reward Redeemed!",
                     f"You successfully redeemed your reward: {item_name}.",
                     "redemption")

    conn.commit()
    return {
        "success": True,
        "message": f"Successfully redeemed {item_name}!",
        "new_balance": balance,
        "reward_result": reward_result
    }


# ─── Rewards History & Certificates Query ──────────────────────────────────────

def get_user_rewards_history(conn, user_id: int, user_role: str):
    """Returns the immutable point transaction ledger for a user."""
    cur = conn.cursor()
    cur.execute('''
        SELECT transaction_id, transaction_type, points, balance_after, description, reference_id, created_at
        FROM reward_transactions
        WHERE user_id=? AND user_role=?
        ORDER BY transaction_id DESC
    ''', (user_id, user_role))
    return [dict(r) for r in cur.fetchall()]


def get_user_certificates(conn, user_id: int, user_role: str):
    """Returns all earned and redeemed certificates for a user."""
    cur = conn.cursor()
    cur.execute('''
        SELECT certificate_id, cert_code, recipient_name, cert_type, milestone_title,
               milestone_count, issued_date, pdf_path, created_at
        FROM reward_certificates
        WHERE user_id=? AND user_role=?
        ORDER BY certificate_id DESC
    ''', (user_id, user_role))
    return [dict(r) for r in cur.fetchall()]


def get_user_redemptions(conn, user_id: int, user_role: str):
    """Returns past redemptions made by the user."""
    cur = conn.cursor()
    cur.execute('''
        SELECT rr.*, rc.name AS item_name, rc.description AS item_desc, rc.item_type
        FROM reward_redemptions rr
        JOIN reward_catalog rc ON rc.item_key = rr.item_key
        WHERE rr.user_id=? AND rr.user_role=?
        ORDER BY rr.redemption_id DESC
    ''', (user_id, user_role))
    return [dict(r) for r in cur.fetchall()]


# ─── Admin Fraud Reversal & Points Revocation ──────────────────────────────────

def admin_revoke_activity_points(conn, admin_username: str, activity_type: str, activity_id: int, reason: str):
    """
    Revokes points awarded for a fraudulent or reversed donation/delivery.
    Creates an audit transaction, adjusts balances, and recalculates badges.
    """
    cur = conn.cursor()
    if activity_type == 'donation':
        ref_pattern = f"donation_{activity_id}"
        cur.execute('''
            SELECT user_id, user_role, points FROM reward_transactions
            WHERE reference_id = ? AND points > 0
        ''', (ref_pattern,))
    else:
        ref_pattern = f"pickup_{activity_id}"
        cur.execute('''
            SELECT user_id, user_role, points FROM reward_transactions
            WHERE reference_id = ? AND points > 0
        ''', (ref_pattern,))

    rows = cur.fetchall()
    if not rows:
        return {"success": False, "error": f"No reward points found for {activity_type} #{activity_id}"}

    revoked_entries = []
    for r in rows:
        uid = r['user_id']
        role = r['user_role']
        awarded_pts = r['points']
        audit_ref = f"revocation_{activity_type}_{activity_id}_{uuid.uuid4().hex[:6]}"
        desc = f"ADMIN REVOCATION ({reason}): Revoked points for {activity_type} #{activity_id} by {admin_username}"

        _record_point_transaction(conn, uid, role, "revocation", -awarded_pts, desc, audit_ref)

        # Mark donation or pickup as Fraudulent/Reversed if needed
        if activity_type == 'donation':
            cur.execute("UPDATE food_donation SET donation_status='Reversed' WHERE donation_id=?", (activity_id,))
        else:
            cur.execute("UPDATE pickup SET status='Reversed' WHERE pickup_id=?", (activity_id,))

        add_notification(conn, uid, role,
                         "Points Revocation Notice",
                         f"Notice: {awarded_pts} FB Points for {activity_type} #{activity_id} were revoked. Reason: {reason}",
                         "revocation")

        # Recalculate badge eligibility
        _recalculate_badges_after_revocation(conn, uid, role)
        revoked_entries.append({"user_id": uid, "role": role, "points_revoked": awarded_pts})

    conn.commit()
    return {"success": True, "revoked_entries": revoked_entries}


def _recalculate_badges_after_revocation(conn, user_id: int, role: str):
    """Marks badges as revoked if user's completed contributions fall below threshold."""
    cur = conn.cursor()
    if role == 'donor':
        cur.execute("SELECT COUNT(*) FROM food_donation WHERE donor_id=? AND donation_status='Completed'", (user_id,))
        valid_count = cur.fetchone()[0]
        badges = DONOR_BADGES
    else:
        cur.execute("SELECT COUNT(*) FROM pickup WHERE volunteer_id=? AND status='Delivered'", (user_id,))
        valid_count = cur.fetchone()[0]
        badges = VOLUNTEER_BADGES

    for b in badges:
        if valid_count < b['threshold']:
            cur.execute('''
                UPDATE user_achievements
                SET is_revoked = 1
                WHERE user_id=? AND user_role=? AND badge_key=?
            ''', (user_id, role, b['key']))


# ─── Synchronization of Historical Data ───────────────────────────────────────

def sync_existing_records(conn):
    """
    Runs during initialization to award appropriate points & badges for pre-existing
    completed donations and deliveries in the database. Idempotent.
    """
    cur = conn.cursor()
    # Check completed donations
    cur.execute("SELECT donation_id FROM food_donation WHERE donation_status='Completed' ORDER BY donation_id ASC")
    donations = cur.fetchall()
    for d in donations:
        try:
            process_donation_completed(conn, d['donation_id'])
        except Exception as e:
            print(f"[Sync] Error processing donation {d['donation_id']}: {e}")

    # Check delivered pickups
    cur.execute("SELECT pickup_id FROM pickup WHERE status='Delivered' AND volunteer_id IS NOT NULL ORDER BY pickup_id ASC")
    pickups = cur.fetchall()
    for p in pickups:
        try:
            process_delivery_completed(conn, p['pickup_id'])
        except Exception as e:
            print(f"[Sync] Error processing pickup {p['pickup_id']}: {e}")

    conn.commit()
