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
    this.updateHeaderBranding();
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
    const donorField = document.getElementById('donorTypeField');
    if (donorField) donorField.style.display = (role === 'donor') ? 'block' : 'none';
    this.updateHeaderBranding();
  },

  switchAuthMode(mode) {
    this.authMode = mode;
    document.getElementById('modeLoginBtn').classList.toggle('active', mode === 'login');
    document.getElementById('modeSignupBtn').classList.toggle('active', mode === 'signup');

    document.getElementById('loginForm').style.display = (mode === 'login') ? 'block' : 'none';
    document.getElementById('signupForm').style.display = (mode === 'signup') ? 'block' : 'none';
    document.getElementById('authTitle').textContent = (mode === 'login') ? 'Sign In' : 'Create Account';
  },

  // Dynamic Header Branding Updates per Page & Role
  updateHeaderBranding() {
    const logoIcon = document.getElementById('headerLogoIcon');
    const logoBox = document.getElementById('headerLogoBox');
    const tagline = document.getElementById('headerBrandTagline');

    if (!logoIcon || !tagline) return;

    if (this.activeView === 'view-landing') {
      logoIcon.className = 'ri-leaf-fill';
      if (logoBox) logoBox.style.background = 'linear-gradient(135deg, #10b981, #047857)';
      tagline.textContent = 'Zero Surplus Waste';
    } else if (this.activeView === 'view-auth') {
      if (this.authRole === 'donor') {
        logoIcon.className = 'ri-shopping-bag-3-fill';
        if (logoBox) logoBox.style.background = 'linear-gradient(135deg, #10b981, #059669)';
        tagline.textContent = 'Donor Account';
      } else if (this.authRole === 'ngo') {
        logoIcon.className = 'ri-heart-pulse-fill';
        if (logoBox) logoBox.style.background = 'linear-gradient(135deg, #6366f1, #4338ca)';
        tagline.textContent = 'NGO Portal';
      } else if (this.authRole === 'volunteer') {
        logoIcon.className = 'ri-motorbike-fill';
        if (logoBox) logoBox.style.background = 'linear-gradient(135deg, #f59e0b, #d97706)';
        tagline.textContent = 'Volunteer Hub';
      }
    } else if (this.activeView === 'view-donor') {
      logoIcon.className = 'ri-shopping-bag-3-fill';
      if (logoBox) logoBox.style.background = 'linear-gradient(135deg, #10b981, #059669)';
      tagline.textContent = 'Donor Workspace';
    } else if (this.activeView === 'view-ngo') {
      logoIcon.className = 'ri-heart-pulse-fill';
      if (logoBox) logoBox.style.background = 'linear-gradient(135deg, #6366f1, #4338ca)';
      tagline.textContent = 'NGO Workspace';
    } else if (this.activeView === 'view-volunteer') {
      logoIcon.className = 'ri-motorbike-fill';
      if (logoBox) logoBox.style.background = 'linear-gradient(135deg, #f59e0b, #d97706)';
      tagline.textContent = 'Volunteer Workspace';
    }

    // Also sync Auth section banner logo badge if on view-auth
    const authBox = document.getElementById('authRoleLogoBox');
    const authIcon = document.getElementById('authRoleLogoIcon');
    const authTitle = document.getElementById('authBannerTitle');
    const authSub = document.getElementById('authBannerSubtitle');

    if (authBox && authIcon && authTitle) {
      if (this.authRole === 'donor') {
        authBox.className = 'workspace-logo-badge donor';
        authIcon.className = 'ri-shopping-bag-3-fill';
        authTitle.textContent = 'Donor Portal';
        if (authSub) authSub.textContent = 'Sign in or create account to donate surplus food';
      } else if (this.authRole === 'ngo') {
        authBox.className = 'workspace-logo-badge ngo';
        authIcon.className = 'ri-heart-pulse-fill';
        authTitle.textContent = 'NGO Portal';
        if (authSub) authSub.textContent = 'Sign in or register your relief shelter & NGO';
      } else if (this.authRole === 'volunteer') {
        authBox.className = 'workspace-logo-badge volunteer';
        authIcon.className = 'ri-motorbike-fill';
        authTitle.textContent = 'Volunteer Hub';
        if (authSub) authSub.textContent = 'Sign in or sign up to deliver food packages';
      }
    }
  },

  updateBottomNavState() {
    document.querySelectorAll('.mobile-bottom-nav .nav-item').forEach(btn => btn.classList.remove('active'));

    const primaryLabel = document.getElementById('navPrimaryLabel');
    const secondaryLabel = document.getElementById('navSecondaryLabel');
    const primaryIcon = document.getElementById('navPrimaryIcon');
    const secondaryIcon = document.getElementById('navSecondaryIcon');

    let activeNavId = 'navHomeBtn';

    if (this.currentUser) {
      const role = this.currentUser.role;
      const subTab = this.activeSubTab[role] || '';

      if (role === 'donor') {
        if (primaryLabel) primaryLabel.textContent = 'Donate';
        if (primaryIcon) primaryIcon.className = 'ri-add-circle-fill';
        if (secondaryLabel) secondaryLabel.textContent = 'Journey';
        if (secondaryIcon) secondaryIcon.className = 'ri-route-fill';

        if (this.activeView === 'view-donor') {
          if (subTab === 'profile') activeNavId = 'navProfileBtn';
          else if (subTab === 'journey') activeNavId = 'navSecondaryBtn';
          else activeNavId = 'navPrimaryBtn';
        }
      } else if (role === 'ngo') {
        if (primaryLabel) primaryLabel.textContent = 'Feed';
        if (primaryIcon) primaryIcon.className = 'ri-restaurant-2-fill';
        if (secondaryLabel) secondaryLabel.textContent = 'Orders';
        if (secondaryIcon) secondaryIcon.className = 'ri-truck-fill';

        if (this.activeView === 'view-ngo') {
          if (subTab === 'profile') activeNavId = 'navProfileBtn';
          else if (subTab === 'orders') activeNavId = 'navSecondaryBtn';
          else activeNavId = 'navPrimaryBtn';
        }
      } else if (role === 'volunteer') {
        if (primaryLabel) primaryLabel.textContent = 'Pickups';
        if (primaryIcon) primaryIcon.className = 'ri-navigation-fill';
        if (secondaryLabel) secondaryLabel.textContent = 'My Tasks';
        if (secondaryIcon) secondaryIcon.className = 'ri-task-fill';

        if (this.activeView === 'view-volunteer') {
          if (subTab === 'profile') activeNavId = 'navProfileBtn';
          else if (subTab === 'mine') activeNavId = 'navSecondaryBtn';
          else activeNavId = 'navPrimaryBtn';
        }
      }
    } else {
      if (primaryLabel) primaryLabel.textContent = 'Sign In';
      if (primaryIcon) primaryIcon.className = 'ri-login-circle-fill';
      if (secondaryLabel) secondaryLabel.textContent = 'Explore';
      if (secondaryIcon) secondaryIcon.className = 'ri-compass-3-fill';

      if (this.activeView === 'view-auth') activeNavId = 'navPrimaryBtn';
      else if (this.activeView === 'view-landing') activeNavId = 'navHomeBtn';
    }

    if (this.activeView === 'view-landing') {
      activeNavId = 'navHomeBtn';
    }

    document.getElementById(activeNavId)?.classList.add('active');
  },

  navigateBottomNav(navType) {
    if (navType === 'home') {
      this.showView('view-landing');
    } else if (navType === 'primary') {
      if (this.currentUser) {
        this.showView(`view-${this.currentUser.role}`);
        if (this.currentUser.role === 'donor') this.switchDonorSubTab('post');
        if (this.currentUser.role === 'ngo') this.switchNgoSubTab('feed');
        if (this.currentUser.role === 'volunteer') this.switchVolSubTab('open');
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
        this.showView('view-landing');
      }
    } else if (navType === 'profile') {
      if (this.currentUser) {
        this.showView(`view-${this.currentUser.role}`);
        if (this.currentUser.role === 'donor') this.switchDonorSubTab('profile');
        if (this.currentUser.role === 'ngo') this.switchNgoSubTab('profile');
        if (this.currentUser.role === 'volunteer') this.switchVolSubTab('profile');
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
      donor_type: document.getElementById('signupDonorType')?.value || 'Individual',
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
      if (this.activeSubTab.donor === 'rewards') this.loadRewardsData('donor');
    } else if (role === 'ngo') {
      this.loadNgoStats();
      this.loadNgoProfile();
      this.loadNgoAvailable();
      if (this.activeSubTab.ngo === 'impact') this.loadNgoImpactData();
    } else if (role === 'volunteer') {
      this.loadVolStats();
      this.loadVolProfile();
      this.loadVolPickups();
      if (this.activeSubTab.volunteer === 'rewards') this.loadRewardsData('volunteer');
    }
    this.checkRewardNotifications();
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
    if (subTab === 'rewards') this.loadRewardsData('donor');
    this.updateBottomNavState();
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
    const cookedAt = document.getElementById('postCookedAt')?.value || '';
    const foodCategory = document.getElementById('postFoodCategory')?.value || 'Vegetarian';
    const photoFile = document.getElementById('postFoodPhoto')?.files[0];

    const formData = new FormData();
    formData.append('food_type', foodType);
    formData.append('quantity', quantity);
    formData.append('time', time);
    formData.append('date_of_donation', date);
    if (cookedAt) formData.append('cooked_at', cookedAt);
    formData.append('food_category', foodCategory);
    if (photoFile) formData.append('food_photo', photoFile);

    try {
      const res = await fetch('/api/donations', {
        method: 'POST',
        body: formData
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
        if (d.volunteer_name) {
          const volCardBtn = d.volunteer_id ? `<button type="button" class="btn btn-sm btn-subtle" style="margin-left:6px;padding:2px 8px;font-size:11px;" onclick="app.showVolunteerCard(${d.volunteer_id})"><i class="ri-id-card-line"></i> View Volunteer Card</button>` : '';
          journeyInfo.push(`<div>🚴 <strong>Volunteer:</strong> ${d.volunteer_name} (${d.volunteer_contact || 'N/A'})${volCardBtn}</div>`);
        }
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
            ${d.food_photo ? `<img src="/food-photo/${d.food_photo}" class="item-food-thumb" alt="Food Photo">` : ''}
            <div class="item-meta-grid">
              <div class="meta-item"><i class="ri-hashtag"></i> ID #${d.donation_id}</div>
              <div class="meta-item"><i class="ri-goblet-line"></i> ${d.quantity} Meals</div>
              <div class="meta-item">${d.food_category === 'Non-Vegetarian' ? '<span class="food-category-badge non-veg">🔴 Non-Veg</span>' : '<span class="food-category-badge veg">🟢 Veg</span>'}</div>
              <div class="meta-item"><i class="ri-calendar-line"></i> ${d.date_of_donation || 'Today'}</div>
              <div class="meta-item"><i class="ri-time-line"></i> Until ${d.time || 'N/A'}</div>
              ${d.cooked_at ? `<div class="meta-item"><i class="ri-timer-line"></i> Cooked: ${d.cooked_at.replace('T', ' ')}</div>` : ''}
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
      this.loadDonorVerificationStatus();
    } catch (e) {}
  },

  async loadDonorVerificationStatus() {
    try {
      const res = await fetch('/api/donor/verification-status');
      const data = await res.json();
      if (data.success) {
        const v = data.verification;
        const badge = document.getElementById('fssaiBadge');
        const statusDiv = document.getElementById('fssaiVerStatusDisplay');
        const inputFssai = document.getElementById('donorFssaiNo');
        
        if (v.fssai_no && inputFssai) inputFssai.value = v.fssai_no;
        
        if (v.verification_status === 'Verified') {
          if (badge) badge.style.display = 'inline-flex';
          if (statusDiv) statusDiv.innerHTML = `<div class="status-banner verified"><i class="ri-checkbox-circle-fill"></i> Verified FSSAI License: <strong>${v.fssai_no || ''}</strong></div>`;
        } else if (v.verification_status === 'Pending') {
          if (badge) badge.style.display = 'none';
          if (statusDiv) statusDiv.innerHTML = `<div class="status-banner pending"><i class="ri-time-line"></i> Verification Pending Admin Review (${v.fssai_no || ''})</div>`;
        } else if (v.verification_status === 'Rejected') {
          if (badge) badge.style.display = 'none';
          if (statusDiv) statusDiv.innerHTML = `<div class="status-banner rejected"><i class="ri-close-circle-fill"></i> Verification Rejected: ${v.rejection_reason || 'Please re-upload valid documents.'}</div>`;
        } else {
          if (badge) badge.style.display = 'none';
          if (statusDiv) statusDiv.innerHTML = '';
        }
      }
    } catch (e) {}
  },

  async submitDonorVerification(e) {
    e.preventDefault();
    const fssaiNo = document.getElementById('donorFssaiNo').value.trim();
    const fileInput = document.getElementById('donorFssaiCert');
    
    if (fssaiNo.length !== 14 || !/^\d{14}$/.test(fssaiNo)) {
      this.showToast('FSSAI number must be exactly 14 digits', 'error');
      return;
    }
    
    const formData = new FormData();
    formData.append('fssai_no', fssaiNo);
    if (fileInput && fileInput.files[0]) {
      formData.append('fssai_cert', fileInput.files[0]);
    }
    
    try {
      const res = await fetch('/api/donor/submit-verification', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.success) {
        this.showToast(data.message || 'Submitted for verification!', 'success');
        this.loadDonorVerificationStatus();
      } else {
        this.showToast(data.error || 'Submission failed', 'error');
      }
    } catch (err) {
      this.showToast('Network error submitting verification', 'error');
    }
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
    if (subTab === 'impact') this.loadNgoImpactData();
    this.updateBottomNavState();
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
          ${d.food_photo_url ? `<img src="${d.food_photo_url}" class="item-food-thumb" alt="Food Photo">` : ''}
          <div class="item-meta-grid">
            <div class="meta-item"><i class="ri-goblet-line"></i> <strong>${d.quantity}</strong> Meals</div>
            <div class="meta-item">${d.food_category === 'Non-Vegetarian' ? '<span class="food-category-badge non-veg">🔴 Non-Veg</span>' : '<span class="food-category-badge veg">🟢 Veg</span>'}</div>
            <div class="meta-item"><i class="ri-store-line"></i> ${d.donor_name} ${d.donor_fssai_verified ? '<span class="verified-badge"><i class="ri-shield-check-fill"></i> FSSAI Verified</span>' : ''}</div>
            <div class="meta-item"><i class="ri-star-fill" style="color:var(--amber);"></i> Rating: ${d.donor_rating} / 5</div>
            ${d.cooked_at ? `<div class="meta-item"><i class="ri-timer-line"></i> Cooked: ${d.cooked_at.replace('T', ' ')}</div>` : ''}
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
      this.loadNgoVerificationStatus();
    } catch (e) {}
  },

  async loadNgoVerificationStatus() {
    try {
      const res = await fetch('/api/ngo/verification-status');
      const data = await res.json();
      if (data.success) {
        const v = data.verification;
        const badge = document.getElementById('ngoBadge');
        const statusDiv = document.getElementById('ngoVerStatusDisplay');
        const darpanInput = document.getElementById('ngoDarpanId');
        const contactPersonInput = document.getElementById('ngoContactPerson');
        const contactPhoneInput = document.getElementById('ngoContactPhone');

        if (v.darpan_id && darpanInput) darpanInput.value = v.darpan_id;
        if (v.contact_person && contactPersonInput) contactPersonInput.value = v.contact_person;
        if (v.contact_phone && contactPhoneInput) contactPhoneInput.value = v.contact_phone;

        if (v.verification_status === 'Verified') {
          if (badge) badge.style.display = 'inline-flex';
          if (statusDiv) statusDiv.innerHTML = `<div class="status-banner verified"><i class="ri-checkbox-circle-fill"></i> Verified NGO (Darpan ID: <strong>${v.darpan_id || ''}</strong>)</div>`;
        } else if (v.verification_status === 'Pending') {
          if (badge) badge.style.display = 'none';
          if (statusDiv) statusDiv.innerHTML = `<div class="status-banner pending"><i class="ri-time-line"></i> Verification Pending Admin Review (Darpan ID: ${v.darpan_id || ''})</div>`;
        } else if (v.verification_status === 'Rejected') {
          if (badge) badge.style.display = 'none';
          if (statusDiv) statusDiv.innerHTML = `<div class="status-banner rejected"><i class="ri-close-circle-fill"></i> Verification Rejected: ${v.rejection_reason || 'Please re-upload valid documents.'}</div>`;
        } else {
          if (badge) badge.style.display = 'none';
          if (statusDiv) statusDiv.innerHTML = `<div class="status-banner pending" style="background:rgba(244,63,94,0.1);color:var(--rose);border-color:rgba(244,63,94,0.2);"><i class="ri-alert-line"></i> Unverified: Please submit NGO verification to accept food donations.</div>`;
        }
      }
    } catch (e) {}
  },

  async submitNgoVerification(e) {
    e.preventDefault();
    const darpanId = document.getElementById('ngoDarpanId').value.trim();
    const regType = document.getElementById('ngoRegType').value;
    const certFile = document.getElementById('ngoRegCert')?.files[0];
    const reg12a = document.getElementById('ngoReg12a')?.value.trim();
    const reg80g = document.getElementById('ngoReg80g')?.value.trim();
    const contactPerson = document.getElementById('ngoContactPerson').value.trim();
    const contactPhone = document.getElementById('ngoContactPhone').value.trim();

    const formData = new FormData();
    formData.append('darpan_id', darpanId);
    formData.append('registration_type', regType);
    if (certFile) formData.append('registration_cert', certFile);
    if (reg12a) formData.append('reg_12a_no', reg12a);
    if (reg80g) formData.append('reg_80g_no', reg80g);
    formData.append('contact_person', contactPerson);
    formData.append('contact_phone', contactPhone);

    try {
      const res = await fetch('/api/ngo/submit-verification', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.success) {
        this.showToast(data.message || 'NGO verification submitted!', 'success');
        this.loadNgoVerificationStatus();
      } else {
        this.showToast(data.error || 'Submission failed', 'error');
      }
    } catch (err) {
      this.showToast('Network error submitting NGO verification', 'error');
    }
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
    if (subTab === 'rewards') this.loadRewardsData('volunteer');
    this.updateBottomNavState();
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
                <div>🏪 <strong>Pickup From:</strong> ${p.donor_name} ${p.donor_fssai_status === 'Verified' ? '<span class="verified-badge"><i class="ri-shield-check-fill"></i> FSSAI Verified</span>' : ''} (${p.donor_address || 'N/A'})</div>
                <div>⭐ <strong>Donor Hygiene:</strong> ${p.donor_rating} / 5.0</div>
                <div>🥗 <strong>Category:</strong> ${p.food_category === 'Non-Vegetarian' ? '<span class="food-category-badge non-veg">🔴 Non-Veg</span>' : '<span class="food-category-badge veg">🟢 Veg</span>'}</div>
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
                  <div>🥗 <strong>Category:</strong> ${p.food_category === 'Non-Vegetarian' ? '<span class="food-category-badge non-veg">🔴 Non-Veg</span>' : '<span class="food-category-badge veg">🟢 Veg</span>'}</div>
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
      this.loadVolVerificationStatus();
    } catch (e) {}
  },

  async loadVolVerificationStatus() {
    try {
      const res = await fetch('/api/volunteer/verification-status');
      const data = await res.json();
      if (data.success) {
        const v = data.verification;
        const badge = document.getElementById('volVerBadge');
        const statusDiv = document.getElementById('volVerStatusDisplay');
        const vehInput = document.getElementById('volVehicleReg');
        const emNameInput = document.getElementById('volEmergencyName');
        const emPhoneInput = document.getElementById('volEmergencyPhone');

        if (v.vehicle_reg_no && vehInput) vehInput.value = v.vehicle_reg_no;
        if (v.emergency_contact_name && emNameInput) emNameInput.value = v.emergency_contact_name;
        if (v.emergency_contact_phone && emPhoneInput) emPhoneInput.value = v.emergency_contact_phone;

        if (v.verification_status === 'Verified') {
          if (badge) badge.style.display = 'inline-flex';
          if (statusDiv) statusDiv.innerHTML = `<div class="status-banner verified"><i class="ri-checkbox-circle-fill"></i> Verified Volunteer (ID & Selfie approved)</div>`;
        } else if (v.verification_status === 'Pending') {
          if (badge) badge.style.display = 'none';
          if (statusDiv) statusDiv.innerHTML = `<div class="status-banner pending"><i class="ri-time-line"></i> Identity Verification Pending Admin Review</div>`;
        } else if (v.verification_status === 'Rejected') {
          if (badge) badge.style.display = 'none';
          if (statusDiv) statusDiv.innerHTML = `<div class="status-banner rejected"><i class="ri-close-circle-fill"></i> Identity Verification Rejected: ${v.rejection_reason || 'Please submit valid ID & selfie.'}</div>`;
        } else {
          if (badge) badge.style.display = 'none';
          if (statusDiv) statusDiv.innerHTML = `<div class="status-banner pending" style="background:rgba(244,63,94,0.1);color:var(--rose);border-color:rgba(244,63,94,0.2);"><i class="ri-alert-line"></i> Unverified: Please submit photo ID & selfie to accept pickup tasks.</div>`;
        }
      }
    } catch (e) {}
  },

  async submitVolVerification(e) {
    e.preventDefault();
    const photoId = document.getElementById('volPhotoId')?.files[0];
    const selfie = document.getElementById('volSelfie')?.files[0];
    const vehicleReg = document.getElementById('volVehicleReg')?.value.trim();
    const dl = document.getElementById('volDl')?.files[0];
    const emName = document.getElementById('volEmergencyName')?.value.trim();
    const emPhone = document.getElementById('volEmergencyPhone')?.value.trim();

    if (!photoId || !selfie) {
      this.showToast('Photo ID and Selfie are required', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('photo_id', photoId);
    formData.append('selfie', selfie);
    if (vehicleReg) formData.append('vehicle_reg_no', vehicleReg);
    if (dl) formData.append('driving_licence', dl);
    if (emName) formData.append('emergency_contact_name', emName);
    if (emPhone) formData.append('emergency_contact_phone', emPhone);

    try {
      const res = await fetch('/api/volunteer/submit-verification', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.success) {
        this.showToast(data.message || 'Volunteer verification submitted!', 'success');
        this.loadVolVerificationStatus();
      } else {
        this.showToast(data.error || 'Submission failed', 'error');
      }
    } catch (err) {
      this.showToast('Network error submitting volunteer verification', 'error');
    }
  },

  async showVolunteerCard(volunteerId) {
    if (!volunteerId) return;
    try {
      const res = await fetch(`/api/volunteer/card/${volunteerId}`);
      const data = await res.json();
      if (data.success) {
        const v = data.card;
        const body = document.getElementById('volCardBody');
        if (!body) return;

        const avatarSrc = v.selfie_url ? v.selfie_url : 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=150&q=80';
        const isVerified = v.verification_status === 'Verified';

        body.innerHTML = `
          <div class="vol-card-profile">
            <img src="${avatarSrc}" class="vol-card-avatar" alt="Volunteer Photo">
            <div class="vol-card-name">
              ${v.name}
              ${isVerified ? '<span class="verified-badge vol-badge"><i class="ri-verified-badge-fill"></i> Verified</span>' : '<span class="badge badge-pending">Unverified</span>'}
            </div>
            <div class="vol-card-meta">
              <div><i class="ri-phone-line"></i> <strong>Contact:</strong> ${v.contact_no || 'Provided upon pickup'}</div>
              <div><i class="ri-car-line"></i> <strong>Vehicle Type:</strong> ${v.vehicle_type || 'Standard'}</div>
              <div><i class="ri-roadster-line"></i> <strong>Vehicle Reg No:</strong> ${v.vehicle_reg_no || 'Not registered'}</div>
              <div><i class="ri-shield-check-line"></i> <strong>Status:</strong> ${v.verification_status}</div>
            </div>
          </div>
        `;
        document.getElementById('volCardModal').classList.add('active');
      } else {
        this.showToast(data.error || 'Could not load volunteer card', 'error');
      }
    } catch (e) {
      this.showToast('Network error loading volunteer card', 'error');
    }
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
  // REWARDS & RECOGNITION SYSTEM CONTROLLER
  // ------------------------------------------------------------------------
  rewardsCache: {
    donor: null,
    volunteer: null,
    ngo: null,
    leaderboardType: { donor: 'monthly', volunteer: 'monthly' }
  },

  async loadRewardsData(role) {
    try {
      const res = await fetch('/api/rewards/summary');
      const data = await res.json();
      if (!data.success) return;

      const d = data.data;
      this.rewardsCache[role] = d;

      if (role === 'donor') {
        const balEl = document.getElementById('donorRewardBal');
        if (balEl) balEl.textContent = d.available_points;
        const ltEl = document.getElementById('donorRewardLifetime');
        if (ltEl) ltEl.textContent = d.lifetime_points;
        const badgeEl = document.getElementById('donorRewardBadge');
        if (badgeEl) badgeEl.textContent = d.current_badge;
        const nextPreviewEl = document.getElementById('donorBadgeNextPreview');
        if (nextPreviewEl) nextPreviewEl.textContent = `Next: ${d.next_badge}`;

        // Streak
        const curStreakEl = document.getElementById('donorStreakCurrent');
        if (curStreakEl) curStreakEl.textContent = `${d.current_streak} Months`;
        const longStreakEl = document.getElementById('donorStreakLongest');
        if (longStreakEl) longStreakEl.textContent = `${d.longest_streak} Months`;
        const nextStreakEl = document.getElementById('donorStreakNext');
        if (nextStreakEl) {
          const nextTarget = d.current_streak < 2 ? 2 : d.current_streak < 3 ? 3 : d.current_streak < 6 ? 6 : 12;
          nextStreakEl.textContent = `Next: ${nextTarget}-Month Streak`;
        }

        // Impact Stats
        const impDonEl = document.getElementById('donorImpactDonations');
        if (impDonEl) impDonEl.textContent = d.total_successful_donations;
        const impQtyEl = document.getElementById('donorImpactQty');
        if (impQtyEl) impQtyEl.textContent = d.total_quantity_donated;
        const impMealsEl = document.getElementById('donorImpactMeals');
        if (impMealsEl) impMealsEl.textContent = d.estimated_meals_provided;
        const impCertsEl = document.getElementById('donorImpactCerts');
        if (impCertsEl) impCertsEl.textContent = d.certificates_earned_count;

        // Badges Section
        const curBadgeTitle = document.getElementById('donorCurrentBadgeTitle');
        if (curBadgeTitle) curBadgeTitle.textContent = d.current_badge;
        const nextBadgeTitle = document.getElementById('donorNextBadgeTitle');
        if (nextBadgeTitle) nextBadgeTitle.textContent = d.next_badge;
        const badgeProgText = document.getElementById('donorBadgeProgressText');
        if (badgeProgText) badgeProgText.textContent = d.badge_progress;

        this.renderBadgesGrid('donorBadgesGrid', d.badges_earned, d.badges_locked);

        // Opt-in check
        const optCheck = document.getElementById('donorLeaderboardOptInCheck');
        if (optCheck) optCheck.checked = d.leaderboard_opt_in;

        const storeBal = document.getElementById('donorStoreBal');
        if (storeBal) storeBal.textContent = d.available_points;

      } else if (role === 'volunteer') {
        const balEl = document.getElementById('volRewardBal');
        if (balEl) balEl.textContent = d.available_points;
        const ltEl = document.getElementById('volRewardLifetime');
        if (ltEl) ltEl.textContent = d.lifetime_points;
        const badgeEl = document.getElementById('volRewardBadge');
        if (badgeEl) badgeEl.textContent = d.current_badge;
        const nextPreviewEl = document.getElementById('volBadgeNextPreview');
        if (nextPreviewEl) nextPreviewEl.textContent = `Next: ${d.next_badge}`;

        // Impact Stats
        const impDelEl = document.getElementById('volImpactDeliveries');
        if (impDelEl) impDelEl.textContent = d.total_completed_deliveries;
        const impFoodEl = document.getElementById('volImpactFoodTransported');
        if (impFoodEl) impFoodEl.textContent = d.total_food_transported;
        const impMealsEl = document.getElementById('volImpactMeals');
        if (impMealsEl) impMealsEl.textContent = d.estimated_meals_delivered;
        const impCertsEl = document.getElementById('volImpactCerts');
        if (impCertsEl) impCertsEl.textContent = d.certificates_earned_count;

        const curBadgeTitle = document.getElementById('volCurrentBadgeTitle');
        if (curBadgeTitle) curBadgeTitle.textContent = d.current_badge;
        const nextBadgeTitle = document.getElementById('volNextBadgeTitle');
        if (nextBadgeTitle) nextBadgeTitle.textContent = d.next_badge;
        const badgeProgText = document.getElementById('volBadgeProgressText');
        if (badgeProgText) badgeProgText.textContent = d.badge_progress;

        this.renderBadgesGrid('volBadgesGrid', d.badges_earned, d.badges_locked);

        const optCheck = document.getElementById('volLeaderboardOptInCheck');
        if (optCheck) optCheck.checked = d.leaderboard_opt_in;

        const storeBal = document.getElementById('volStoreBal');
        if (storeBal) storeBal.textContent = d.available_points;
      }

      this.loadLeaderboard(role, this.rewardsCache.leaderboardType[role] || 'monthly');
      this.loadCertificates(role);
      this.loadStoreCatalog(role, d.available_points);
      this.loadRedemptions(role);
      this.loadHistory(role);

    } catch (e) {
      console.error("Error loading rewards summary:", e);
    }
  },

  renderBadgesGrid(containerId, earned = [], locked = []) {
    const c = document.getElementById(containerId);
    if (!c) return;

    let html = '';
    earned.forEach(b => {
      html += `
        <div class="badge-card unlocked">
          <div class="badge-icon-box"><i class="${b.icon || 'ri-medal-fill'}"></i></div>
          <div class="badge-card-name">${b.name}</div>
          <div class="badge-card-desc">${b.description}</div>
          <div style="margin-top:6px; font-size:10px; color:var(--primary); font-weight:700;"><i class="ri-check-line"></i> Unlocked</div>
        </div>
      `;
    });

    locked.forEach(b => {
      html += `
        <div class="badge-card locked">
          <div class="badge-icon-box"><i class="ri-lock-2-line"></i></div>
          <div class="badge-card-name">${b.name}</div>
          <div class="badge-card-desc">${b.description}</div>
          <div class="badge-card-progress">${b.progress || ''}</div>
        </div>
      `;
    });

    if (!html) html = '<p class="empty-msg">No badges available.</p>';
    c.innerHTML = html;
  },

  switchLeaderboardType(role, type) {
    this.rewardsCache.leaderboardType[role] = type;
    if (role === 'donor') {
      document.getElementById('donorLbTabMonthly')?.classList.toggle('active', type === 'monthly');
      document.getElementById('donorLbTabAllTime')?.classList.toggle('active', type === 'all_time');
    } else {
      document.getElementById('volLbTabMonthly')?.classList.toggle('active', type === 'monthly');
      document.getElementById('volLbTabAllTime')?.classList.toggle('active', type === 'all_time');
    }
    this.loadLeaderboard(role, type);
  },

  async loadLeaderboard(role, type = 'monthly') {
    const containerId = role === 'donor' ? 'donorLeaderboardList' : 'volLeaderboardList';
    const c = document.getElementById(containerId);
    if (!c) return;

    try {
      const res = await fetch(`/api/rewards/leaderboard?role=${role}&type=${type}`);
      const data = await res.json();
      if (!data.success || !data.leaderboard || data.leaderboard.length === 0) {
        c.innerHTML = '<p class="empty-msg" style="padding:16px;">No contributions logged for this leaderboard period yet.</p>';
        return;
      }

      c.innerHTML = data.leaderboard.map(item => `
        <div class="leaderboard-item">
          <div class="leaderboard-rank ${item.rank <= 3 ? 'rank-' + item.rank : ''}">
            ${item.rank === 1 ? '🥇' : item.rank === 2 ? '🥈' : item.rank === 3 ? '🥉' : item.rank}
          </div>
          <div class="leaderboard-user">
            <div class="user-title">${item.display_name}</div>
            <div class="user-badge"><i class="ri-medal-line"></i> ${item.badge}</div>
          </div>
          <div class="leaderboard-points">
            <div class="pts">${item.points} Pts</div>
            <div class="sub">${item.contributions} ${role === 'donor' ? 'donations' : 'rescues'}</div>
          </div>
        </div>
      `).join('');
    } catch (e) {
      c.innerHTML = '<p class="empty-msg">Unable to load leaderboard.</p>';
    }
  },

  async toggleLeaderboardOptIn(role, isOptIn) {
    try {
      const res = await fetch('/api/rewards/leaderboard/opt-in', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ opt_in: isOptIn })
      });
      const data = await res.json();
      if (data.success) {
        this.showToast(isOptIn ? 'You are now visible on public leaderboards.' : 'You opted out of public leaderboards.', 'info');
        this.loadLeaderboard(role, this.rewardsCache.leaderboardType[role] || 'monthly');
      }
    } catch (e) {}
  },

  async loadCertificates(role) {
    const containerId = role === 'donor' ? 'donorCertificatesList' : 'volCertificatesList';
    const c = document.getElementById(containerId);
    if (!c) return;

    try {
      const res = await fetch('/api/rewards/certificates');
      const data = await res.json();
      if (!data.success || !data.certificates || data.certificates.length === 0) {
        c.innerHTML = '<p class="empty-msg" style="padding:16px;">Complete milestones or redeem rewards to earn official certificates.</p>';
        return;
      }

      c.innerHTML = data.certificates.map(cert => `
        <div class="cert-card-row">
          <div class="cert-meta">
            <div class="cert-title"><i class="ri-award-fill" style="color:var(--amber);"></i> ${cert.milestone_title}</div>
            <div class="cert-id">${cert.cert_code} • Issued ${cert.issued_date}</div>
            <div class="cert-date" style="color:var(--primary); font-weight:600;">
              ${cert.cert_type === 'milestone' ? 'Milestone Honor' : 'Points-Based Recognition'}
            </div>
          </div>
          <div>
            <a href="/api/rewards/certificates/${cert.cert_code}/download" target="_blank" download="${cert.cert_code}.pdf" class="btn btn-sm btn-primary">
              <i class="ri-download-2-line"></i> PDF
            </a>
          </div>
        </div>
      `).join('');
    } catch (e) {
      c.innerHTML = '<p class="empty-msg">Unable to load certificates.</p>';
    }
  },

  async loadStoreCatalog(role, currentBal = 0) {
    const containerId = role === 'donor' ? 'donorStoreGrid' : 'volStoreGrid';
    const c = document.getElementById(containerId);
    if (!c) return;

    try {
      const res = await fetch('/api/rewards/catalog');
      const data = await res.json();
      if (!data.success || !data.catalog) return;

      c.innerHTML = data.catalog.map(item => {
        const canRedeem = currentBal >= item.points_cost;
        return `
          <div class="store-card">
            <div class="store-cost">${item.points_cost} FB Pts</div>
            <div class="store-name">${item.name}</div>
            <div class="store-desc">${item.description}</div>
            <button class="btn btn-sm ${canRedeem ? 'btn-primary' : 'btn-subtle'}"
              ${!canRedeem ? 'disabled' : ''}
              onclick="app.redeemStoreReward('${item.key}', ${item.points_cost}, '${role}')">
              ${canRedeem ? '<i class="ri-gift-line"></i> Redeem' : 'Need More Pts'}
            </button>
          </div>
        `;
      }).join('');
    } catch (e) {}
  },

  async redeemStoreReward(itemKey, cost, role) {
    if (!confirm(`Redeem this digital recognition reward for ${cost} FoodBridge Points?`)) {
      return;
    }

    try {
      const res = await fetch('/api/rewards/redeem', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_key: itemKey })
      });
      const data = await res.json();
      if (data.success) {
        this.showToast(data.message || 'Reward redeemed successfully!', 'success');
        this.loadRewardsData(role);
      } else {
        this.showToast(data.error || 'Redemption failed', 'error');
      }
    } catch (e) {
      this.showToast('Redemption request failed', 'error');
    }
  },

  async loadRedemptions(role) {
    const containerId = role === 'donor' ? 'donorRedemptionsList' : 'volRedemptionsList';
    const c = document.getElementById(containerId);
    if (!c) return;

    try {
      const res = await fetch('/api/rewards/redemptions');
      const data = await res.json();
      if (!data.success || !data.redemptions || data.redemptions.length === 0) {
        c.innerHTML = '<p class="empty-msg" style="padding:12px;">No past redemptions recorded.</p>';
        return;
      }

      c.innerHTML = data.redemptions.map(r => `
        <div class="cert-card-row">
          <div class="cert-meta">
            <div class="cert-title">${r.item_name}</div>
            <div class="cert-id">Spent ${r.points_spent} FB Points • ${r.created_at}</div>
          </div>
          <span class="status-badge status-Verified">Redeemed</span>
        </div>
      `).join('');
    } catch (e) {}
  },

  async loadHistory(role) {
    const containerId = role === 'donor' ? 'donorHistoryList' : 'volHistoryList';
    const c = document.getElementById(containerId);
    if (!c) return;

    try {
      const res = await fetch('/api/rewards/history');
      const data = await res.json();
      if (!data.success || !data.history || data.history.length === 0) {
        c.innerHTML = '<p class="empty-msg" style="padding:16px;">No transactions logged yet.</p>';
        return;
      }

      c.innerHTML = data.history.map(t => {
        const isPos = t.points > 0;
        return `
          <div class="history-item-row">
            <div class="history-desc">
              <div class="act-name">${t.description}</div>
              <div class="act-date">${t.created_at} • Bal: ${t.balance_after} pts</div>
            </div>
            <div class="history-pts ${isPos ? 'positive' : 'negative'}">
              ${isPos ? '+' : ''}${t.points} FB
            </div>
          </div>
        `;
      }).join('');
    } catch (e) {
      c.innerHTML = '<p class="empty-msg">Unable to load ledger.</p>';
    }
  },

  // ------------------------------------------------------------------------
  // NGO IMPACT RECOGNITION CONTROLLER
  // ------------------------------------------------------------------------
  async loadNgoImpactData() {
    try {
      const res = await fetch('/api/ngo/impact-summary');
      const data = await res.json();
      if (!data.success) return;

      const d = data.data;
      document.getElementById('ngoImpactMealsDist').textContent = d.estimated_meals_distributed;
      document.getElementById('ngoImpactBadge').textContent = d.current_badge;
      document.getElementById('ngoImpactDistCount').textContent = d.total_verified_distributions;
      document.getElementById('ngoImpactQtyRec').textContent = d.total_food_received;
      document.getElementById('ngoImpactDonationsRec').textContent = d.total_donations_received;
      document.getElementById('ngoStatVerifiedDist').textContent = d.total_verified_distributions;
      document.getElementById('ngoStatPendingDist').textContent = (d.pending_confirmations || []).length;

      // Badges Grid
      this.renderBadgesGrid('ngoBadgesGrid', d.badges_earned, d.badges_locked);

      // Populate Delivery Select Dropdown
      const select = document.getElementById('ngoDistDeliverySelect');
      if (select) {
        select.innerHTML = '<option value="">-- Choose Received Delivery --</option>' +
          (d.pending_confirmations || []).map(p => `
            <option value="${p.delivery_id}" data-qty="${p.quantity}">
              Order #${p.delivery_id}: ${p.food_type} (${p.quantity} portions) from ${p.donor_name}
            </option>
          `).join('');
      }

      // Default distribution date to today
      const dateInp = document.getElementById('ngoDistDateInput');
      if (dateInp && !dateInp.value) {
        dateInp.value = new Date().toISOString().split('T')[0];
      }

      // History
      const histEl = document.getElementById('ngoDistHistoryList');
      if (histEl) {
        if (!d.confirmed_history || d.confirmed_history.length === 0) {
          histEl.innerHTML = '<p class="empty-msg">No verified distributions confirmed yet.</p>';
        } else {
          histEl.innerHTML = d.confirmed_history.map(h => `
            <div class="cert-card-row">
              <div class="cert-meta">
                <div class="cert-title">${h.food_type} — ${h.meals_distributed} Meals</div>
                <div class="cert-id">To: ${h.beneficiary_group} • Date: ${h.distributed_date}</div>
                ${h.notes ? `<div class="cert-date" style="color:var(--text-muted);">${h.notes}</div>` : ''}
              </div>
              <span class="status-badge status-Verified"><i class="ri-check-line"></i> Verified</span>
            </div>
          `).join('');
        }
      }

    } catch (e) {
      console.error("Error loading NGO impact data:", e);
    }
  },

  onNgoDeliverySelectChange() {
    const select = document.getElementById('ngoDistDeliverySelect');
    const mealsInput = document.getElementById('ngoDistMealsInput');
    if (!select || !mealsInput) return;
    const opt = select.options[select.selectedIndex];
    const qty = opt.getAttribute('data-qty');
    if (qty) {
      mealsInput.value = qty;
    }
  },

  async submitNgoDistributionConfirmation(e) {
    e.preventDefault();
    const delivery_id = document.getElementById('ngoDistDeliverySelect').value;
    const meals_distributed = document.getElementById('ngoDistMealsInput').value;
    const distributed_date = document.getElementById('ngoDistDateInput').value;
    const beneficiary_group = document.getElementById('ngoDistBeneficiaryInput').value.trim();
    const notes = document.getElementById('ngoDistNotesInput').value.trim();

    try {
      const res = await fetch('/api/ngo/confirm-distribution', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          delivery_id, meals_distributed, distributed_date, beneficiary_group, notes
        })
      });
      const data = await res.json();
      if (data.success) {
        this.showToast('Distribution confirmed and impact verified!', 'success');
        document.getElementById('ngoDistConfirmForm')?.reset();
        this.loadNgoImpactData();
      } else {
        this.showToast(data.error || 'Confirmation failed', 'error');
      }
    } catch (e) {
      this.showToast('Failed to submit distribution confirmation', 'error');
    }
  },

  // ------------------------------------------------------------------------
  // In-App Reward Notifications Polling
  // ------------------------------------------------------------------------
  async checkRewardNotifications() {
    if (!this.currentUser) return;
    try {
      const res = await fetch('/api/rewards/notifications');
      const data = await res.json();
      if (data.success && data.notifications && data.notifications.length > 0) {
        data.notifications.forEach(n => {
          this.showToast(`🏆 ${n.title}: ${n.message}`, 'success');
        });
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
