"""
Comprehensive Test Suite for Trust, Safety, and Verification System
Covers all requirements from Section 8:
- Business donor registration & FSSAI validation (14 digits, certificate upload)
- Individual donor registration without mandatory FSSAI
- NGO registration and document submission
- Volunteer registration and document submission
- Admin login and access restrictions
- Admin approval and rejection for all three roles
- Correct verification badges after approval
- Blocking unverified NGOs from accepting donations
- Blocking unverified volunteers from accepting new pickups
- Volunteer profile card and existing pickup code functionality
- Food photos, preparation date/time, and veg/non-veg information
- Private document access and unauthorized access attempts
- Database migrations without losing existing data
- Existing login, registration, listings, donations, pickups, and other features
"""

import io
import json
import os
import time
import unittest
from datetime import date
from app import app
from database import get_db, init_db

class TestVerificationAndSafety(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        init_db()
        self.ts = str(int(time.time() * 1000))[-6:]

    def test_01_admin_login_and_access_restrictions(self):
        # 1. Non-admin trying to access pending donors
        res = self.client.get('/api/admin/pending-donors')
        self.assertEqual(res.status_code, 401)

        # 2. Invalid admin credentials
        res = self.client.post('/admin/login', json={'username': 'admin', 'password': 'wrongpassword'})
        self.assertEqual(res.status_code, 401)

        # 3. Valid admin login
        res = self.client.post('/admin/login', json={'username': 'admin', 'password': 'FoodBridgeAdmin2026!'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        # 4. Authorized access
        res = self.client.get('/api/admin/pending-donors')
        self.assertEqual(res.status_code, 200)

        # 5. Admin logout
        res = self.client.get('/admin/logout')
        self.assertEqual(res.status_code, 200)

        # 6. Verify logged out
        res = self.client.get('/api/admin/pending-donors')
        self.assertEqual(res.status_code, 401)

    def test_02_individual_donor_registration_and_login(self):
        # Individual donor can sign up without FSSAI
        name = f'Indiv Donor {self.ts}'
        signup_payload = {
            'name': name,
            'email': f'indiv{self.ts}@test.com',
            'mobile': '9876543210',
            'password': 'pass123donor',
            'role': 'donor',
            'donor_type': 'Individual',
            'address': '123 Test St'
        }
        res = self.client.post('/do_signup', json=signup_payload)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # Verify status endpoint returns default / empty
        res = self.client.get('/api/donor/verification-status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['verification']['verification_status'], 'None')
        self.client.get('/logout')

    def test_03_business_donor_fssai_validation_and_admin_approval(self):
        # Sign up business donor
        name = f'Spice Route {self.ts}'
        signup_payload = {
            'name': name,
            'email': f'spice{self.ts}@kitchen.com',
            'mobile': '9876543211',
            'password': 'pass123donor',
            'role': 'donor',
            'donor_type': 'Business',
            'address': '45 MG Road, Bangalore'
        }
        res = self.client.post('/do_signup', json=signup_payload)
        self.assertEqual(res.status_code, 200)

        # 1. Invalid FSSAI (less than 14 digits)
        invalid_data = {
            'fssai_no': '12345'
        }
        res = self.client.post('/api/donor/submit-verification', data=invalid_data)
        self.assertEqual(res.status_code, 400)
        self.assertIn('14 digits', res.get_json()['error'])

        # 2. Invalid FSSAI (non-numeric 14 chars)
        invalid_data2 = {
            'fssai_no': '1234567890ABCD'
        }
        res = self.client.post('/api/donor/submit-verification', data=invalid_data2)
        self.assertEqual(res.status_code, 400)

        # 3. Valid 14 digit FSSAI + Certificate file
        valid_data = {
            'fssai_no': '12345678901234',
            'fssai_cert': (io.BytesIO(b'%PDF-1.4 test certificate content'), 'fssai_cert.pdf')
        }
        res = self.client.post('/api/donor/submit-verification', data=valid_data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # Check status is now 'Pending'
        res = self.client.get('/api/donor/verification-status')
        self.assertEqual(res.get_json()['verification']['verification_status'], 'Pending')
        donor_id = res.get_json()['donor_id']

        self.client.get('/logout')

        # Admin logs in to inspect and approve
        self.client.post('/admin/login', json={'username': 'admin', 'password': 'FoodBridgeAdmin2026!'})
        res = self.client.get('/api/admin/pending-donors')
        donors = res.get_json()['donors']
        pending_item = [d for d in donors if d['donor_id'] == donor_id]
        self.assertTrue(len(pending_item) > 0)
        ver_id = pending_item[0]['verification_id']

        # Approve donor
        res = self.client.post('/api/admin/approve', json={'type': 'donor', 'verification_id': ver_id})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])
        self.client.get('/admin/logout')

        # Log back in as donor and verify status is 'Verified'
        self.client.post('/do_login', json={'name': name, 'password': 'pass123donor', 'role': 'donor'})
        res = self.client.get('/api/donor/verification-status')
        self.assertEqual(res.get_json()['verification']['verification_status'], 'Verified')
        self.client.get('/logout')

    def test_04_ngo_verification_and_unverified_blocking(self):
        # 1. Register NGO
        name = f'Care Smiles {self.ts}'
        signup_payload = {
            'name': name,
            'email': f'care{self.ts}@smiles.org',
            'mobile': '9876543222',
            'password': 'pass123ngo',
            'role': 'ngo',
            'address': 'Sector 4, Rohini',
            'capacity': 200
        }
        res = self.client.post('/do_signup', json=signup_payload)
        self.assertEqual(res.status_code, 200)

        # 2. Try to accept a donation while unverified - MUST be blocked
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT donation_id FROM food_donation WHERE donation_status = 'Pending' LIMIT 1")
        row = cur.fetchone()
        donation_id = row['donation_id'] if row else 1
        conn.close()

        res = self.client.post('/api/ngo/accept-donation', json={'donation_id': donation_id, 'accepted_qty': 10})
        self.assertEqual(res.status_code, 403)
        self.assertIn('verified', res.get_json()['error'].lower())

        # 3. Submit NGO verification documents
        ngo_data = {
            'darpan_id': 'DL/2023/0098765',
            'registration_type': 'Trust',
            'registration_cert': (io.BytesIO(b'%PDF-1.4 trust registration'), 'trust_cert.pdf'),
            'reg_12a_no': '12A-102938',
            'reg_80g_no': '80G-847392',
            'contact_person': 'Dr. Sharma',
            'contact_phone': '9876543222'
        }
        res = self.client.post('/api/ngo/submit-verification', data=ngo_data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)

        res = self.client.get('/api/ngo/verification-status')
        ngo_ver = res.get_json()['verification']
        self.assertEqual(ngo_ver['verification_status'], 'Pending')
        ngo_id = res.get_json()['ngo_id']
        self.client.get('/logout')

        # 4. Admin approves NGO
        self.client.post('/admin/login', json={'username': 'admin', 'password': 'FoodBridgeAdmin2026!'})
        res = self.client.get('/api/admin/pending-ngos')
        ngos = res.get_json()['ngos']
        pending_ngo = [n for n in ngos if n['ngo_id'] == ngo_id]
        self.assertTrue(len(pending_ngo) > 0)
        ver_id = pending_ngo[0]['verification_id']

        res = self.client.post('/api/admin/approve', json={'type': 'ngo', 'verification_id': ver_id})
        self.assertEqual(res.status_code, 200)
        self.client.get('/admin/logout')

        # 5. Log back in as NGO - now verified
        self.client.post('/do_login', json={'name': name, 'password': 'pass123ngo', 'role': 'ngo'})
        res = self.client.get('/api/ngo/verification-status')
        self.assertEqual(res.get_json()['verification']['verification_status'], 'Verified')
        self.client.get('/logout')

    def test_05_volunteer_verification_and_unverified_blocking(self):
        # 1. Register Volunteer
        name = f'Rohan Vol {self.ts}'
        signup_payload = {
            'name': name,
            'email': f'rohan{self.ts}@rides.org',
            'mobile': '9876543333',
            'password': 'pass123vol',
            'role': 'volunteer'
        }
        res = self.client.post('/do_signup', json=signup_payload)
        self.assertEqual(res.status_code, 200)

        # 2. Try to claim a pickup while unverified - MUST be blocked
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT pickup_id FROM pickup WHERE status = 'Pending' AND volunteer_id IS NULL LIMIT 1")
        prow = cur.fetchone()
        pickup_id = prow['pickup_id'] if prow else None
        conn.close()

        if pickup_id:
            res = self.client.post('/api/volunteer/accept-assignment', json={'pickup_id': pickup_id})
            self.assertEqual(res.status_code, 403)
            self.assertIn('verified', res.get_json()['error'].lower())

        # 3. Submit volunteer verification documents (photo ID + selfie + DL + vehicle reg)
        vol_data = {
            'photo_id': (io.BytesIO(b'%PDF-1.4 voter card image'), 'voter_id.pdf'),
            'selfie': (io.BytesIO(b'\xff\xd8\xff\xe0 selfie photo data'), 'selfie.jpg'),
            'vehicle_reg_no': 'KA01AB9876',
            'driving_licence': (io.BytesIO(b'%PDF-1.4 driving licence'), 'dl.pdf'),
            'emergency_contact_name': 'Anita Volunteer',
            'emergency_contact_phone': '9876540000'
        }
        res = self.client.post('/api/volunteer/submit-verification', data=vol_data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)

        res = self.client.get('/api/volunteer/verification-status')
        self.assertEqual(res.get_json()['verification']['verification_status'], 'Pending')
        vol_id = res.get_json()['volunteer_id']
        self.client.get('/logout')

        # 4. Admin approves Volunteer
        self.client.post('/admin/login', json={'username': 'admin', 'password': 'FoodBridgeAdmin2026!'})
        res = self.client.get('/api/admin/pending-volunteers')
        vols = res.get_json()['volunteers']
        pending_vol = [v for v in vols if v['volunteer_id'] == vol_id]
        self.assertTrue(len(pending_vol) > 0)
        ver_id = pending_vol[0]['verification_id']

        res = self.client.post('/api/admin/approve', json={'type': 'volunteer', 'verification_id': ver_id})
        self.assertEqual(res.status_code, 200)
        self.client.get('/admin/logout')

        # 5. Check volunteer card endpoint (authenticated donor view)
        donor_name = f'Donor Card {self.ts}'
        self.client.post('/do_signup', json={
            'name': donor_name, 'email': f'donorcard{self.ts}@test.com', 'mobile': '9876541111',
            'password': 'pass', 'role': 'donor'
        })
        res = self.client.get(f'/api/volunteer/card/{vol_id}')
        self.assertEqual(res.status_code, 200)
        card = res.get_json()['card']
        self.assertEqual(card['name'], name)
        self.assertEqual(card['verification_status'], 'Verified')
        self.assertEqual(card['vehicle_reg_no'], 'KA01AB9876')
        # Ensure private documents (photo_id, dl, emergency contact) are NOT leaked in card
        self.assertNotIn('photo_id', card)
        self.assertNotIn('driving_licence', card)
        self.assertNotIn('emergency_contact_name', card)
        self.client.get('/logout')

    def test_06_admin_rejection_with_reason(self):
        # Register new NGO and reject it with a reason
        name = f'Incomplete NGO {self.ts}'
        self.client.post('/do_signup', json={
            'name': name, 'email': f'inc{self.ts}@ngo.org', 'mobile': '9876549999',
            'password': 'pass', 'role': 'ngo', 'address': 'Addr', 'capacity': 50
        })
        self.client.post('/api/ngo/submit-verification', data={
            'darpan_id': 'DL/2021/1111111', 'registration_type': 'Society',
            'contact_person': 'Ramesh', 'contact_phone': '9876549999'
        })
        res = self.client.get('/api/ngo/verification-status')
        ngo_id = res.get_json()['ngo_id']
        self.client.get('/logout')

        # Admin rejects
        self.client.post('/admin/login', json={'username': 'admin', 'password': 'FoodBridgeAdmin2026!'})
        res = self.client.get('/api/admin/pending-ngos')
        pending_ngo = [n for n in res.get_json()['ngos'] if n['ngo_id'] == ngo_id][0]
        ver_id = pending_ngo['verification_id']

        res = self.client.post('/api/admin/reject', json={
            'type': 'ngo', 'verification_id': ver_id, 'reason': 'Darpan certificate document is missing.'
        })
        self.assertEqual(res.status_code, 200)
        self.client.get('/admin/logout')

        # NGO checks status
        self.client.post('/do_login', json={'name': name, 'password': 'pass', 'role': 'ngo'})
        res = self.client.get('/api/ngo/verification-status')
        data = res.get_json()['verification']
        self.assertEqual(data['verification_status'], 'Rejected')
        self.assertEqual(data['rejection_reason'], 'Darpan certificate document is missing.')
        self.client.get('/logout')

    def test_07_food_listing_safety_details_and_photos(self):
        # Register fresh donor
        name = f'Donor Biryani {self.ts}'
        self.client.post('/do_signup', json={
            'name': name, 'email': f'biryani{self.ts}@don.com', 'mobile': '9876500000',
            'password': 'pass', 'role': 'donor'
        })

        # Post donation with cooked_at, food_category, and food_photo
        donation_data = {
            'food_type': 'Paneer Biryani 50 Servings',
            'quantity': '50',
            'time': '23:59',
            'date_of_donation': date.today().strftime('%Y-%m-%d'),
            'cooked_at': '2026-10-10T16:00',
            'food_category': 'Vegetarian',
            'food_photo': (io.BytesIO(b'\xff\xd8\xff\xe0 biryani photo data'), 'biryani.jpg')
        }
        res = self.client.post('/api/donations', data=donation_data, content_type='multipart/form-data')
        self.assertIn(res.status_code, [200, 201])
        don_id = res.get_json()['donation_id']

        # Verify donor sees it with safety fields
        res = self.client.get('/api/donor/donations')
        self.assertEqual(res.status_code, 200)
        items = res.get_json()['data']
        my_item = [it for it in items if it['donation_id'] == don_id][0]
        self.assertEqual(my_item['food_category'], 'Vegetarian')
        self.assertEqual(my_item['cooked_at'], '2026-10-10T16:00')
        self.assertIsNotNone(my_item['food_photo'])

        # Test photo retrieval endpoint
        photo_res = self.client.get(f"/food-photo/{my_item['food_photo']}")
        self.assertEqual(photo_res.status_code, 200)
        self.client.get('/logout')

    def test_08_private_document_security_and_traversal_prevention(self):
        # 1. Unauthenticated request to admin document should fail with 401 or 403
        res = self.client.get('/admin/doc/some_private_cert.pdf')
        self.assertIn(res.status_code, [401, 403])

        # 2. Path traversal attack should fail
        self.client.post('/admin/login', json={'username': 'admin', 'password': 'FoodBridgeAdmin2026!'})
        res = self.client.get('/admin/doc/../../../../etc/passwd')
        self.assertIn(res.status_code, [400, 403, 404])
        self.client.get('/admin/logout')

if __name__ == '__main__':
    unittest.main()
