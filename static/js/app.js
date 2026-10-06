/* ==========================================================================
   FoodBridge Mobile — Unified Frontend Application Controller
   ========================================================================== */

const app = {
  // Application State
  currentUser: null,
  currentRole: 'donor', // 'donor' | 'ngo' | 'volunteer'
  authRole: 'donor',
  authMode: 'login',
  activeView: 'view-landing',
  activeSubTab: {
    donor: 'post',
    ngo: 'feed',
    volunteer: 'open'
  },
  pendingModalData: {},
  feedbackRating: 5,
  refreshTimer: null,

  // ------------------------------------------------------------------------
  // Initialization
  // ------------------------------------------------------------------------
  init() {
    this.updateNotchTime();
    setInterval(() => this.updateNotchTime(), 60000);
    this.bindEvents();
    this.checkSession();
    this.loadPublicStats();
    this.startAutoRefresh();
  },

  updateNotchTime() {
    const now = new Date();
    const hrs = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    const el = document.getElementById('notchTime');
    if (el) el.textContent = `${hrs}:${mins}`;
  },

  bindEvents() {
    // Theme toggle
    document.getElementById('themeToggleBtn')?.addEventListener('click', () => this.toggleTheme());
    
    // Desktop Mobile Frame expand toggle
    document.getElementById('frameToggleBtn')?.addEventListener('click', () => this.toggleFrameExpand());

    // Brand logo click
    document.getElementById('brandBtn')?.addEventListener('click', () => this.showView('view-landing'));

    // Landing buttons
    document.getElementById('landingGetStartedBtn')?.addEventListener('click', () => this.showAuthView('donor'));
    document.getElementById('landingExploreBtn')?.addEventListener('click', () => {
      window.scrollTo({ top: 300, behavior: 'smooth' });
    });

    // Logout
    document.getElementById('logoutBtn')?.addEventListener('click', () => this.logout());

    // Modal close backdrops
    document.querySelectorAll('.modal-backdrop').forEach(modal => {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
      });
    });

    // Star rating picker
    document.querySelectorAll('#starRatingBox .star-item').forEach(star => {
      star.addEventListener('click', (e) => {
        const val = parseInt(e.target.getAttribute('data-val'));
        this.feedbackRating = val;
        document.querySelectorAll('#starRatingBox .star-item').forEach((s, idx) => {
          s.classList.toggle('active', idx < val);
        });
      });
    });

    // Modal action buttons
    document.getElementById('confirmAcceptBtn')?.addEventListener('click', () => this.confirmAcceptDonation());
    document.getElementById('confirmFeedbackBtn')?.addEventListener('click', () => this.confirmFeedback());
    document.getElementById('confirmOtpBtn')?.addEventListener('click', () => this.confirmOtpDelivery());
  },

  // ------------------------------------------------------------------------
  // UI Theme & Frame Toggles
  // ------------------------------------------------------------------------
  toggleTheme() {
    const body = document.body;
    const isDark = body.classList.contains('dark-theme');
    body.classList.toggle('dark-theme', !isDark);
    document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
    document.getElementById('themeIcon').className = isDark ? 'ri-sun-line' : 'ri-moon-line';
  },

  toggleFrameExpand() {
    const frame = document.getElementById('mobileFrame');
    const isExpanded = frame.classList.contains('expanded');
    frame.classList.toggle('expanded', !isExpanded);
    document.getElementById('frameIcon').className = isExpanded ? 'ri-cellphone-line' : 'ri-fullscreen-exit-line';
  },

  showToast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast-item ${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
  },

  // ------------------------------------------------------------------------
  // View & Navigation Routing
  // ------------------------------------------------------------------------
  showView(viewId) {
    document.querySelectorAll('.app-view').forEach(v => v.classList.remove('active'));
    const target = document.getElementById(viewId);
    if (target) {
      target.classList.add('active');
      this.activeView = viewId;
    }
    this.updateBottomNavState();
  },

  selectRole(role) {
    if (this.currentUser && this.currentUser.role === role) {
      this.showView(`view-${role}`);
    } else {
      this.showAuthView(role);
    }
  },

  showAuthView(role = 'donor') {
    this.authRole = role;
    this.switchAuthRole(role);
    this.showView('view-auth');
  },

  switchAuthRole(role) {
    this.authRole = role;
    document.querySelectorAll('.role-pill').forEach(pill => {
      pill.classList.toggle('active', pill.getAttribute('data-role') === role);
    });

    const ngoExtra = document.getElementById('ngoExtraFields');
    if (ngoExtra) ngoExtra.style.display = (role === 'ngo') ? 'block' : 'none';
  },

  switchAuthMode(mode) {
    this.authMode = mode;
    document.getElementById('modeLoginBtn').classList.toggle('active', mode === 'login');
    document.getElementById('modeSignupBtn').classList.toggle('active', mode === 'signup');

    document.getElementById('loginForm').style.display = (mode === 'login') ? 'block' : 'none';
    document.getElementById('signupForm').style.display = (mode === 'signup') ? 'block' : 'none';
    document.getElementById('authTitle').textContent = (mode === 'login') ? 'Sign In' : 'Create Account';
  },

  updateBottomNavState() {
    document.querySelectorAll('.mobile-bottom-nav .nav-item').forEach(btn => btn.classList.remove('active'));

    const primaryLabel = document.getElementById('navPrimaryLabel');
    const secondaryLabel = document.getElementById('navSecondaryLabel');

    if (this.currentUser) {
      if (this.currentUser.role === 'donor') {
        if (primaryLabel) primaryLabel.textContent = 'Donate';
        if (secondaryLabel) secondaryLabel.textContent = 'Journey';
      } else if (this.currentUser.role === 'ngo') {
        if (primaryLabel) primaryLabel.textContent = 'Feed';
        if (secondaryLabel) secondaryLabel.textContent = 'Orders';
      } else if (this.currentUser.role === 'volunteer') {
        if (primaryLabel) primaryLabel.textContent = 'Pickups';
        if (secondaryLabel) secondaryLabel.textContent = 'My Tasks';
      }
    } else {
      if (primaryLabel) primaryLabel.textContent = 'Actions';
      if (secondaryLabel) secondaryLabel.textContent = 'Feed';
    }

    if (this.activeView === 'view-landing') {
      document.getElementById('navHomeBtn')?.classList.add('active');
    } else if (this.activeView.startsWith('view-')) {
      document.getElementById('navPrimaryBtn')?.classList.add('active');
    }
  },

  navigateBottomNav(navType) {
    if (navType === 'home') {
      this.showView('view-landing');
    } else if (navType === 'profile') {
      if (this.currentUser) {
        this.showView(`view-${this.currentUser.role}`);
        if (this.currentUser.role === 'donor') this.switchDonorSubTab('profile');
        if (this.currentUser.role === 'ngo') this.switchNgoSubTab('profile');
        if (this.currentUser.role === 'volunteer') this.switchVolSubTab('profile');
      } else {
        this.showAuthView('donor');
      }
    } else if (navType === 'primary') {
      if (this.currentUser) {
        this.showView(`view-${this.currentUser.role}`);
      } else {
        this.showAuthView('donor');
      }
    } else if (navType === 'secondary') {
      if (this.currentUser) {
        this.showView(`view-${this.currentUser.role}`);
        if (this.currentUser.role === 'donor') this.switchDonorSubTab('journey');
        if (this.currentUser.role === 'ngo') this.switchNgoSubTab('orders');
        if (this.currentUser.role === 'volunteer') this.switchVolSubTab('mine');
      } else {
        this.showAuthView('donor');
      }
    }
  },

  // ------------------------------------------------------------------------
  // Session & Authentication Handlers
  // ------------------------------------------------------------------------
  async checkSession() {
    try {
      const res = await fetch('/api/me');
      const data = await res.json();
      if (data.authenticated) {
        this.currentUser = data;
        this.updateUserChip();
        this.loadDashboardData();
        this.showView(`view-${data.role}`);
      } else {
        this.currentUser = null;
        this.updateUserChip();
      }
    } catch (e) {
      console.error("Session check error:", e);
    }
  },

  updateUserChip() {
    const chip = document.getElementById('userChip');
    if (!chip) return;
    if (this.currentUser) {
      chip.style.display = 'flex';
      document.getElementById('userRoleBadge').textContent = this.currentUser.role;
      document.getElementById('userNameText').textContent = this.currentUser.user_name;
    } else {
      chip.style.display = 'none';
    }
  },

  async handleLogin(e) {
    e.preventDefault();
    const name = document.getElementById('loginName').value.trim();
    const password = document.getElementById('loginPassword').value.trim();

    try {
      const res = await fetch('/do_login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, password, role: this.authRole })
      });
      const data = await res.json();
      if (data.success) {
        this.showToast(`Welcome back, ${data.user_name}!`, 'success');
        this.checkSession();
      } else {
        this.showToast(data.error || 'Login failed', 'error');
      }
    } catch (err) {
      this.showToast('Network error during login', 'error');
    }
  },

  async handleSignup(e) {
    e.preventDefault();
    const payload = {
      name: document.getElementById('signupName').value.trim(),
      email: document.getElementById('signupEmail').value.trim(),
      mobile: document.getElementById('signupMobile').value.trim(),
      password: document.getElementById('signupPassword').value.trim(),
      role: this.authRole,
      address: document.getElementById('signupAddress')?.value.trim() || '',
      capacity: document.getElementById('signupCapacity')?.value.trim() || '100',
      priority: document.getElementById('signupPriority')?.value || 'Medium'
    };

    try {
      const res = await fetch('/do_signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        this.showToast(`Account created successfully!`, 'success');
        this.checkSession();
      } else {
        this.showToast(data.error || 'Signup failed', 'error');
      }
    } catch (err) {
      this.showToast('Network error during signup', 'error');
    }
  },

  async quickLogin(name, password, role) {
    this.authRole = role;
    document.getElementById('loginName').value = name;
    document.getElementById('loginPassword').value = password;
    this.handleLogin(new Event('submit'));
  },

  async logout() {
    try {
      await fetch('/logout');
      this.currentUser = null;
      this.updateUserChip();
      this.showToast('Logged out', 'info');
      this.showView('view-landing');
    } catch (e) {
      console.error(e);
    }
  },

  // ------------------------------------------------------------------------
  // Data Loading Router
  // ------------------------------------------------------------------------
  loadDashboardData() {
    if (!this.currentUser) return;
    const role = this.currentUser.role;
    if (role === 'donor') {
      this.loadDonorStats();
      this.loadDonorProfile();
      this.loadDonorDonations();
    } else if (role === 'ngo') {
      this.loadNgoStats();
      this.loadNgoProfile();
      this.loadNgoAvailable();
    } else if (role === 'volunteer') {
      this.loadVolStats();
      this.loadVolProfile();
      this.loadVolPickups();
    }
  },

  async loadPublicStats() {
    try {
      const res = await fetch('/api/dashboard');
      const data = await res.json();
      if (data.success) {
        const s = data.stats;
        document.getElementById('pubMealCount').textContent = s.total_donations * 25 + 50;
        document.getElementById('pubDonorCount').textContent = s.total_donors;
        document.getElementById('pubNgoCount').textContent = s.total_ngos;
        document.getElementById('pubVolCount').textContent = s.available_volunteers + 2;
      }
    } catch (e) {}
  },

  // ------------------------------------------------------------------------
  // DONOR WORKSPACE LOGIC
  // ------------------------------------------------------------------------
  switchDonorSubTab(subTab, el) {
    this.activeSubTab.donor = subTab;
    document.querySelectorAll('#view-donor .subtab-content').forEach(s => s.classList.remove('active'));
    document.getElementById(`donor-sub-${subTab}`)?.classList.add('active');
    
    if (el) {
      document.querySelectorAll('#view-donor .segment-btn').forEach(b => b.classList.remove('active'));
      el.classList.add('active');
    }

    if (subTab === 'journey') this.loadDonorDonations();
    if (subTab === 'wasted') this.loadDonorWasted();
    if (subTab === 'feedback') this.loadDonorFeedback();
    if (subTab === 'profile') this.loadDonorProfile();
  },

  async loadDonorStats() {
    try {
      const res = await fetch('/api/donor/stats');
      const data = await res.json();
      if (data.success) {
        const s = data.stats;
        document.getElementById('donorStatTotal').textContent = s.total;
        document.getElementById('donorStatPending').textContent = s.pending;
        document.getElementById('donorStatAccepted').textContent = s.accepted;
        document.getElementById('donorStatCompleted').textContent = s.completed;
        document.getElementById('donorStatWasted').textContent = s.wasted;
      }
    } catch (e) {}
  },

  async submitDonation(e) {
    e.preventDefault();
    const foodType = document.getElementById('postFoodType').value.trim();
    const quantity = document.getElementById('postQuantity').value;
    const time = document.getElementById('postTime').value;
    const date = document.getElementById('postDate').value;

    try {
      const res = await fetch('/api/donations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ food_type: foodType, quantity, time, date_of_donation: date })
      });
      const data = await res.json();
      if (data.success) {
        this.showToast(`Donation #${data.donation_id} posted!`, 'success');
        document.getElementById('postDonationForm').reset();
        this.loadDonorStats();
        this.switchDonorSubTab('journey');
      } else {
        this.showToast(data.error || 'Failed to post donation', 'error');
      }
    } catch (err) {
      this.showToast('Network error posting donation', 'error');
    }
  },

  async loadDonorDonations() {
    try {
      const res = await fetch('/api/donor/donations');
      const data = await res.json();
      const container = document.getElementById('donorDonationsList');
      if (!container) return;

      if (!data.data || data.data.length === 0) {
        container.innerHTML = `
          <div class="empty-placeholder">
            <i class="ri-restaurant-line"></i>
            <p>No active donations posted yet.</p>
          </div>`;
        return;
      }

      container.innerHTML = data.data.map(d => {
        const statusBadgeClass = `badge-${d.donation_status.toLowerCase().replace(' ', '')}`;
        let cancelBtn = '';
        if (d.donation_status === 'Pending') {
          cancelBtn = `<button class="btn btn-sm btn-danger" onclick="app.deleteDonation(${d.donation_id})">Cancel</button>`;
        }

        let journeyInfo = [];
        if (d.ngo_name) journeyInfo.push(`<div>🏠 <strong>NGO:</strong> ${d.ngo_name}</div>`);
        if (d.volunteer_name) journeyInfo.push(`<div>🚴 <strong>Volunteer:</strong> ${d.volunteer_name} (${d.volunteer_contact || 'N/A'})</div>`);
        if (d.pickup_status) journeyInfo.push(`<div>📦 <strong>Pickup:</strong> ${d.pickup_status}</div>`);
        if (d.otp_code && d.pickup_status !== 'Delivered') {
          journeyInfo.push(`<div>🔑 <strong>Security OTP:</strong> <span class="otp-box">${d.otp_code}</span></div>`);
        }
        if (d.delivery_status) journeyInfo.push(`<div>🚚 <strong>Delivery:</strong> ${d.delivery_status}</div>`);

        return `
          <div class="item-feed-card">
            <div class="item-card-header">
              <span class="item-title">${d.food_type}</span>
              <span class="badge ${statusBadgeClass}">${d.donation_status}</span>
            </div>
            <div class="item-meta-grid">
              <div class="meta-item"><i class="ri-hashtag"></i> ID #${d.donation_id}</div>
              <div class="meta-item"><i class="ri-goblet-line"></i> ${d.quantity} Meals</div>
              <div class="meta-item"><i class="ri-calendar-line"></i> ${d.date_of_donation || 'Today'}</div>
              <div class="meta-item"><i class="ri-time-line"></i> Until ${d.time || 'N/A'}</div>
            </div>
            ${journeyInfo.length > 0 ? `<div class="journey-timeline-box">${journeyInfo.join('')}</div>` : ''}
            <div style="margin-top: 10px; display: flex; justify-content: flex-end;">${cancelBtn}</div>
          </div>`;
      }).join('');
    } catch (e) {
      console.error(e);
    }
  },

  async deleteDonation(donationId) {
    if (!confirm('Are you sure you want to cancel this pending donation?')) return;
    try {
      const res = await fetch(`/api/donations/${donationId}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        this.showToast('Donation cancelled', 'info');
        this.loadDonorStats();
        this.loadDonorDonations();
      }
    } catch (e) {}
  },

  async loadDonorWasted() {
    try {
      const res = await fetch('/api/donor/wasted-donations');
      const data = await res.json();
      const container = document.getElementById('donorWastedList');
      if (!container) return;

      if (!data.data || data.data.length === 0) {
        container.innerHTML = `<div class="empty-placeholder"><i class="ri-checkbox-circle-line"></i><p>Zero food wasted! Great job.</p></div>`;
        return;
      }

      container.innerHTML = data.data.map(d => `
        <div class="item-feed-card">
          <div class="item-card-header">
            <span class="item-title">${d.food_type}</span>
            <span class="badge badge-wasted">Wasted</span>
          </div>
          <div class="item-meta-grid">
            <div class="meta-item"><i class="ri-goblet-line"></i> ${d.quantity} Meals</div>
            <div class="meta-item"><i class="ri-calendar-line"></i> Expired on ${d.date_of_donation || 'N/A'}</div>
          </div>
        </div>`).join('');
    } catch (e) {}
  },

  async loadDonorFeedback() {
    try {
      const res = await fetch('/api/donor/feedback-received');
      const data = await res.json();
      const container = document.getElementById('donorFeedbackList');
      if (!container) return;

      if (!data.data || data.data.length === 0) {
        container.innerHTML = `<div class="empty-placeholder"><i class="ri-star-line"></i><p>No feedback received from NGOs yet.</p></div>`;
        return;
      }

      container.innerHTML = data.data.map(f => `
        <div class="item-feed-card">
          <div class="item-card-header">
            <span class="item-title">Rating from ${f.ngo_name}</span>
            <span class="star-rating-display">⭐ ${f.rating} / 5</span>
          </div>
          <p style="font-size:12px; color: var(--text-muted); margin-bottom: 6px;">"${f.comments || 'No comments provided.'}"</p>
          <div style="font-size:11px; color: var(--primary); font-weight: 600;">Hygiene Score: ${f.hygiene_score} / 5</div>
        </div>`).join('');
    } catch (e) {}
  },

  async loadDonorProfile() {
    try {
      const res = await fetch('/api/donor/profile');
      const data = await res.json();
      if (!data.error) {
        document.getElementById('donorProfName').value = data.donor_name || '';
        document.getElementById('donorProfContact').value = data.contact_no || '';
        document.getElementById('donorProfAddress').value = data.address || '';
        document.getElementById('donorProfEmail').value = data.email || '';
        document.getElementById('donorHygieneDisplay').textContent = `⭐ ${data.hygiene_rating || 5.0} / 5.0`;
      }
    } catch (e) {}
  },

  async saveDonorProfile(e) {
    e.preventDefault();
    const payload = {
      donor_name: document.getElementById('donorProfName').value.trim(),
      contact_no: document.getElementById('donorProfContact').value.trim(),
      address: document.getElementById('donorProfAddress').value.trim(),
      email: document.getElementById('donorProfEmail').value.trim()
    };
    try {
      const res = await fetch('/api/donor/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        this.showToast('Profile updated!', 'success');
        this.checkSession();
      }
    } catch (err) {}
  },

  // ------------------------------------------------------------------------
  // NGO WORKSPACE LOGIC
  // ------------------------------------------------------------------------
  switchNgoSubTab(subTab, el) {
    this.activeSubTab.ngo = subTab;
    document.querySelectorAll('#view-ngo .subtab-content').forEach(s => s.classList.remove('active'));
    document.getElementById(`ngo-sub-${subTab}`)?.classList.add('active');

    if (el) {
      document.querySelectorAll('#view-ngo .segment-btn').forEach(b => b.classList.remove('active'));
      el.classList.add('active');
    }

    if (subTab === 'feed') this.loadNgoAvailable();
    if (subTab === 'orders') this.loadNgoOrders();
    if (subTab === 'feedback') this.loadNgoFeedbackGiven();
    if (subTab === 'wasted') this.loadNgoWasted();
    if (subTab === 'profile') this.loadNgoProfile();
  },

  async loadNgoStats() {
    try {
      const res = await fetch('/api/ngo/stats');
      const data = await res.json();
      if (data.success) {
        const s = data.stats;
        document.getElementById('ngoStatAvailable').textContent = s.available;
        document.getElementById('ngoStatPending').textContent = s.pending;
        document.getElementById('ngoStatDelivered').textContent = s.delivered;
        document.getElementById('ngoStatTotal').textContent = s.total;
      }
    } catch (e) {}
  },

  async loadNgoAvailable() {
    try {
      const res = await fetch('/api/ngo/available-donations');
      const data = await res.json();
      const container = document.getElementById('ngoAvailableFeed');
      if (!container) return;

      if (!data.data || data.data.length === 0) {
        container.innerHTML = `<div class="empty-placeholder"><i class="ri-inbox-line"></i><p>No available surplus food right now.</p></div>`;
        return;
      }

      container.innerHTML = data.data.map(d => `
        <div class="item-feed-card">
          <div class="item-card-header">
            <span class="item-title">${d.food_type}</span>
            <span class="badge badge-pending">Available</span>
          </div>
          <div class="item-meta-grid">
            <div class="meta-item"><i class="ri-goblet-line"></i> <strong>${d.quantity}</strong> Meals</div>
            <div class="meta-item"><i class="ri-store-line"></i> ${d.donor_name}</div>
            <div class="meta-item"><i class="ri-star-fill" style="color:var(--amber);"></i> Rating: ${d.donor_rating} / 5</div>
            <div class="meta-item"><i class="ri-map-pin-line"></i> ${d.donor_address || 'Address on claim'}</div>
          </div>
          <button class="btn btn-primary btn-sm width-full" onclick="app.openAcceptModal(${d.donation_id}, ${d.quantity})">
            Accept Food Donation <i class="ri-check-double-line"></i>
          </button>
        </div>`).join('');
    } catch (e) {}
  },

  openAcceptModal(donationId, availQty) {
    this.pendingModalData.acceptDonationId = donationId;
    this.pendingModalData.acceptAvailQty = availQty;
    document.getElementById('acceptModalAvail').textContent = availQty;
    document.getElementById('acceptQtyInput').value = availQty;
    document.getElementById('acceptModal').classList.add('active');
  },

  closeModal(modalId) {
    document.getElementById(modalId)?.classList.remove('active');
  },

  async confirmAcceptDonation() {
    const donationId = this.pendingModalData.acceptDonationId;
    const acceptedQty = parseInt(document.getElementById('acceptQtyInput').value);

    try {
      const res = await fetch('/api/ngo/accept-donation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ donation_id: donationId, accepted_qty: acceptedQty })
      });
      const data = await res.json();
      if (data.success) {
        this.closeModal('acceptModal');
        this.showToast(data.message, 'success');
        this.loadNgoStats();
        this.loadNgoAvailable();
        this.switchNgoSubTab('orders');
      } else {
        this.showToast(data.error || 'Accept failed', 'error');
      }
    } catch (err) {}
  },

  async loadNgoOrders() {
    try {
      const res = await fetch('/api/ngo/orders');
      const data = await res.json();
      const container = document.getElementById('ngoOrdersFeed');
      if (!container) return;

      if (!data.data || data.data.length === 0) {
        container.innerHTML = `<div class="empty-placeholder"><i class="ri-truck-line"></i><p>No orders claimed yet.</p></div>`;
        return;
      }

      container.innerHTML = data.data.map(o => {
        const isDelivered = o.delivery_status === 'Delivered';
        let actionArea = '';
        if (!isDelivered) {
          actionArea = `<button class="btn btn-success btn-sm" onclick="app.markReceived(${o.delivery_id}, ${o.pickup_id})">Mark Received <i class="ri-check-line"></i></button>`;
        } else {
          actionArea = `<button class="btn btn-outline btn-sm" onclick="app.openFeedbackModal(${o.donation_id})">Submit Feedback <i class="ri-star-line"></i></button>`;
        }

        return `
          <div class="item-feed-card">
            <div class="item-card-header">
              <span class="item-title">${o.food_type} (${o.quantity} Meals)</span>
              <span class="badge ${isDelivered ? 'badge-delivered' : 'badge-progress'}">${o.delivery_status}</span>
            </div>
            <div class="journey-timeline-box">
              <div>🏪 <strong>Donor:</strong> ${o.donor_name} (${o.donor_address || ''})</div>
              <div>🚴 <strong>Volunteer:</strong> ${o.volunteer_name || 'Awaiting Claim'} (${o.volunteer_contact || 'N/A'})</div>
              <div>🔑 <strong>Security OTP:</strong> <span class="otp-box">${o.otp_code || 'Pending'}</span></div>
            </div>
            <div style="margin-top: 10px; display: flex; justify-content: flex-end;">${actionArea}</div>
          </div>`;
      }).join('');
    } catch (e) {}
  },

  async markReceived(deliveryId, pickupId) {
    try {
      const res = await fetch('/api/ngo/mark-received', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ delivery_id: deliveryId, pickup_id: pickupId })
      });
      const data = await res.json();
      if (data.success) {
        this.showToast('Delivery marked as received!', 'success');
        this.loadNgoStats();
        this.loadNgoOrders();
      }
    } catch (e) {}
  },

  openFeedbackModal(donationId) {
    this.pendingModalData.feedbackDonationId = donationId;
    document.getElementById('feedbackCommentInput').value = '';
    document.getElementById('feedbackModal').classList.add('active');
  },

  async confirmFeedback() {
    const donationId = this.pendingModalData.feedbackDonationId;
    const rating = this.feedbackRating;
    const hygieneScore = parseInt(document.getElementById('hygieneScoreInput').value);
    const comments = document.getElementById('feedbackCommentInput').value.trim();

    try {
      const res = await fetch('/api/ngo/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ donation_id: donationId, rating, hygiene_score: hygieneScore, comments })
      });
      const data = await res.json();
      if (data.success) {
        this.closeModal('feedbackModal');
        this.showToast('Feedback submitted to donor!', 'success');
        this.switchNgoSubTab('feedback');
      }
    } catch (e) {}
  },

  async loadNgoFeedbackGiven() {
    try {
      const res = await fetch('/api/ngo/feedback-given');
      const data = await res.json();
      const container = document.getElementById('ngoFeedbackGivenFeed');
      if (!container) return;

      if (!data.data || data.data.length === 0) {
        container.innerHTML = `<div class="empty-placeholder"><i class="ri-star-smile-line"></i><p>No feedback submitted yet.</p></div>`;
        return;
      }

      container.innerHTML = data.data.map(f => `
        <div class="item-feed-card">
          <div class="item-card-header">
            <span class="item-title">Donor: ${f.donor_name}</span>
            <span class="star-rating-display">⭐ ${f.rating} / 5</span>
          </div>
          <p style="font-size:12px; color: var(--text-muted);">"${f.comments || 'No comment'}"</p>
        </div>`).join('');
    } catch (e) {}
  },

  async loadNgoWasted() {
    try {
      const res = await fetch('/api/ngo/wasted-donations');
      const data = await res.json();
      const container = document.getElementById('ngoWastedFeed');
      if (!container) return;

      if (!data.data || data.data.length === 0) {
        container.innerHTML = `<div class="empty-placeholder"><i class="ri-checkbox-circle-line"></i><p>No wasted donations.</p></div>`;
        return;
      }

      container.innerHTML = data.data.map(d => `
        <div class="item-feed-card">
          <div class="item-card-header">
            <span class="item-title">${d.food_type}</span>
            <span class="badge badge-wasted">Wasted</span>
          </div>
          <div class="item-meta-grid">
            <div class="meta-item"><i class="ri-goblet-line"></i> ${d.quantity} Meals</div>
            <div class="meta-item"><i class="ri-calendar-line"></i> ${d.date_of_donation || 'N/A'}</div>
          </div>
        </div>`).join('');
    } catch (e) {}
  },

  async loadNgoProfile() {
    try {
      const res = await fetch('/api/ngo/profile');
      const data = await res.json();
      if (!data.error) {
        document.getElementById('ngoProfName').value = data.ngo_name || '';
        document.getElementById('ngoProfContact').value = data.contact_no || '';
        document.getElementById('ngoProfAddress').value = data.address || '';
        document.getElementById('ngoProfCapacity').value = data.capacity || 100;
        document.getElementById('ngoProfPriority').value = data.priority_level || 'Medium';
      }
    } catch (e) {}
  },

  async saveNgoProfile(e) {
    e.preventDefault();
    const payload = {
      ngo_name: document.getElementById('ngoProfName').value.trim(),
      contact_no: document.getElementById('ngoProfContact').value.trim(),
      address: document.getElementById('ngoProfAddress').value.trim(),
      capacity: document.getElementById('ngoProfCapacity').value,
      priority_level: document.getElementById('ngoProfPriority').value
    };
    try {
      const res = await fetch('/api/ngo/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        this.showToast('NGO Settings Saved!', 'success');
        this.checkSession();
      }
    } catch (e) {}
  },

  // ------------------------------------------------------------------------
  // VOLUNTEER WORKSPACE LOGIC
  // ------------------------------------------------------------------------
  switchVolSubTab(subTab, el) {
    this.activeSubTab.volunteer = subTab;
    document.querySelectorAll('#view-volunteer .subtab-content').forEach(s => s.classList.remove('active'));
    document.getElementById(`vol-sub-${subTab}`)?.classList.add('active');

    if (el) {
      document.querySelectorAll('#view-volunteer .segment-btn').forEach(b => b.classList.remove('active'));
      el.classList.add('active');
    }

    if (subTab === 'open') this.loadVolPickups();
    if (subTab === 'mine') this.loadVolPickups();
    if (subTab === 'wasted') this.loadVolWasted();
    if (subTab === 'profile') this.loadVolProfile();
  },

  async loadVolStats() {
    try {
      const res = await fetch('/api/volunteer/stats');
      const data = await res.json();
      if (data.success) {
        const s = data.stats;
        document.getElementById('volStatTotal').textContent = s.total;
        document.getElementById('volStatPending').textContent = s.pending;
        document.getElementById('volStatProgress').textContent = s.in_progress;
        document.getElementById('volStatDelivered').textContent = s.delivered;
      }
    } catch (e) {}
  },

  async loadVolPickups() {
    try {
      const res = await fetch('/api/volunteer/pickups');
      const data = await res.json();
      const openContainer = document.getElementById('volOpenFeed');
      const myContainer = document.getElementById('volMyFeed');

      // 1. Open Pickups
      if (openContainer) {
        if (!data.available || data.available.length === 0) {
          openContainer.innerHTML = `<div class="empty-placeholder"><i class="ri-motorbike-line"></i><p>No open pickup tasks right now.</p></div>`;
        } else {
          openContainer.innerHTML = data.available.map(p => `
            <div class="item-feed-card">
              <div class="item-card-header">
                <span class="item-title">${p.food_type} (${p.quantity} Meals)</span>
                <span class="badge badge-pending">Open Task</span>
              </div>
              <div class="journey-timeline-box">
                <div>🏪 <strong>Pickup From:</strong> ${p.donor_name} (${p.donor_address || 'N/A'})</div>
                <div>⭐ <strong>Donor Hygiene:</strong> ${p.donor_rating} / 5.0</div>
                <div>🏠 <strong>Deliver To:</strong> ${p.ngo_name} (${p.ngo_address || 'N/A'})</div>
              </div>
              <button class="btn btn-primary btn-sm width-full" style="margin-top:10px;" onclick="app.claimPickup(${p.pickup_id})">
                Claim Pickup Task <i class="ri-hand-coin-line"></i>
              </button>
            </div>`).join('');
        }
      }

      // 2. My Pickups
      if (myContainer) {
        if (!data.data || data.data.length === 0) {
          myContainer.innerHTML = `<div class="empty-placeholder"><i class="ri-task-line"></i><p>No claimed tasks yet.</p></div>`;
        } else {
          myContainer.innerHTML = data.data.map(p => {
            let actionBtn = '';
            if (p.status === 'Pending') {
              actionBtn = `<button class="btn btn-primary btn-sm" onclick="app.updatePickupStatus(${p.pickup_id}, 'In Progress')">Start Pickup <i class="ri-play-fill"></i></button>`;
            } else if (p.status === 'In Progress') {
              actionBtn = `<button class="btn btn-success btn-sm" onclick="app.openOtpModal(${p.pickup_id})">Mark Delivered (Enter OTP) <i class="ri-shield-check-line"></i></button>`;
            } else {
              actionBtn = `<span class="badge badge-delivered">Completed</span>`;
            }

            return `
              <div class="item-feed-card">
                <div class="item-card-header">
                  <span class="item-title">Task #${p.pickup_id} — ${p.food_type}</span>
                  <span class="badge badge-${p.status.toLowerCase().replace(' ', '')}">${p.status}</span>
                </div>
                <div class="journey-timeline-box">
                  <div>🏪 <strong>Pickup:</strong> ${p.donor_name} (${p.donor_contact || 'N/A'})</div>
                  <div>🏠 <strong>Deliver:</strong> ${p.ngo_name} (${p.ngo_contact || 'N/A'})</div>
                  <div>🔑 <strong>Security OTP:</strong> <span class="otp-box">${p.otp_code}</span></div>
                </div>
                <div style="margin-top:10px; display:flex; justify-height: flex-end; justify-content: flex-end;">${actionBtn}</div>
              </div>`;
          }).join('');
        }
      }
    } catch (e) {}
  },

  async claimPickup(pickupId) {
    try {
      const res = await fetch('/api/volunteer/accept-assignment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pickup_id: pickupId })
      });
      const data = await res.json();
      if (data.success) {
        this.showToast(data.message, 'success');
        this.loadVolStats();
        this.loadVolPickups();
        this.switchVolSubTab('mine');
      } else {
        this.showToast(data.error || 'Claim failed', 'error');
      }
    } catch (e) {}
  },

  async updatePickupStatus(pickupId, status, otp = null) {
    try {
      const res = await fetch('/api/volunteer/update-pickup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pickup_id: pickupId, status, otp })
      });
      const data = await res.json();
      if (data.success) {
        this.showToast(data.message, 'success');
        this.loadVolStats();
        this.loadVolPickups();
      } else {
        this.showToast(data.error || 'Status update failed', 'error');
      }
    } catch (e) {}
  },

  openOtpModal(pickupId) {
    this.pendingModalData.otpPickupId = pickupId;
    document.getElementById('otpCodeInput').value = '';
    document.getElementById('otpModal').classList.add('active');
  },

  async confirmOtpDelivery() {
    const pickupId = this.pendingModalData.otpPickupId;
    const otp = document.getElementById('otpCodeInput').value.trim();
    if (!otp) {
      this.showToast('Please enter the 4-digit OTP', 'error');
      return;
    }
    this.closeModal('otpModal');
    this.updatePickupStatus(pickupId, 'Delivered', otp);
  },

  async loadVolWasted() {
    try {
      const res = await fetch('/api/volunteer/wasted-donations');
      const data = await res.json();
      const container = document.getElementById('volWastedFeed');
      if (!container) return;

      if (!data.data || data.data.length === 0) {
        container.innerHTML = `<div class="empty-placeholder"><i class="ri-checkbox-circle-line"></i><p>No wasted donations.</p></div>`;
        return;
      }

      container.innerHTML = data.data.map(d => `
        <div class="item-feed-card">
          <div class="item-card-header">
            <span class="item-title">${d.food_type}</span>
            <span class="badge badge-wasted">Wasted</span>
          </div>
        </div>`).join('');
    } catch (e) {}
  },

  async loadVolProfile() {
    try {
      const res = await fetch('/api/volunteer/profile');
      const data = await res.json();
      if (!data.error) {
        document.getElementById('volProfName').value = data.name || '';
        document.getElementById('volProfContact').value = data.contact_no || '';
        document.getElementById('volProfVehicle').value = data.vehicle_type || 'Bike';
        document.getElementById('volProfStatus').value = data.availability_status || 'Available';
      }
    } catch (e) {}
  },

  async saveVolProfile(e) {
    e.preventDefault();
    const payload = {
      name: document.getElementById('volProfName').value.trim(),
      contact_no: document.getElementById('volProfContact').value.trim(),
      vehicle_type: document.getElementById('volProfVehicle').value,
      availability_status: document.getElementById('volProfStatus').value
    };
    try {
      const res = await fetch('/api/volunteer/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        this.showToast('Profile Saved!', 'success');
        this.checkSession();
      }
    } catch (e) {}
  },

  // ------------------------------------------------------------------------
  // Auto-Refresh Polling
  // ------------------------------------------------------------------------
  startAutoRefresh() {
    this.refreshTimer = setInterval(() => {
      if (this.currentUser) {
        this.loadDashboardData();
      } else {
        this.loadPublicStats();
      }
    }, 15000);
  }
};

// Initialize Application on DOM Ready
document.addEventListener('DOMContentLoaded', () => app.init());
