
    let activeMode = 'product';
    let currentQuery = '';
    let currentDept = 'Ministry of Defence';
    let currentOfficer = 'Shri R. K. Sharma (MoD)';
    let currentRole = 'Indenting Officer';
    let currentMilestone = 'Stage 1: Administrative Approval (A/A)';
    let lastBenchmarkData = null;
    let tableData = [];
    let allTableData = [];
    let goldenParams = [];
    let sortCol = 'tier';
    let sortAsc = true;

    // Snapshot the real results markup once, so the skeleton loader can be
    // swapped back out without losing the result element IDs on re-render.
    const resultsAreaEl = document.getElementById('results-area');
    const resultsAreaTemplate = resultsAreaEl ? resultsAreaEl.innerHTML : '';

    // Load active officer from localStorage
    function getToken() {
      return localStorage.getItem('onyx_token') || '';
    }
    function loadOfficerSession() {
      const stored = localStorage.getItem('onyx_officer');
      if (stored) {
        try {
          const data = JSON.parse(stored);
          if (data.name && data.dept) {
            currentOfficer = `${data.name} (${data.dept})`;
            currentDept = data.dept;
            currentRole = data.role || currentRole;
            const deptInput = document.getElementById('dept-input');
            if (deptInput) deptInput.value = data.dept;
            const officerDisplay = document.getElementById('officer-name-display');
            if (officerDisplay) officerDisplay.textContent = `${data.name} (${data.dept.replace('Ministry of ', '').replace(' / NIC', '')})`;
          }
        } catch (e) {}
      }
      // Recover authenticated session if we have a stored JWT
      const token = localStorage.getItem('onyx_token');
      if (token) {
        fetch('/auth/me', {
          headers: { 'Authorization': 'Bearer ' + token }
        })
          .then(r => { if (r.ok) return r.json(); throw new Error('not-authed'); })
          .then(profile => {
            const data = { name: profile.name || currentOfficer, dept: profile.department || currentDept, role: profile.role || currentRole, email: profile.email || '' };
            localStorage.setItem('onyx_officer', JSON.stringify(data));
            currentOfficer = `${data.name} (${data.dept})`;
            currentDept = data.dept;
            currentRole = data.role;
            const deptInput = document.getElementById('dept-input');
            if (deptInput) deptInput.value = data.dept;
            const officerDisplay = document.getElementById('officer-name-display');
            if (officerDisplay) officerDisplay.textContent = `${data.name} (${data.dept.replace('Ministry of ', '').replace(' / NIC', '')})`;
          })
          .catch(() => {
            // Fall back to cached officer display; do not force logout on stale token
          });
      }
    }

    function switchOfficerRole() {
      const token = localStorage.getItem('onyx_token');
      if (!token) {
        alert('Sign in as a procurement officer to set the certificate identity.');
        window.location.href = '/landing.html#auth';
        return;
      }
      // Refresh the officer identity from the real JWT profile.
      fetch('/auth/me', {
        headers: { 'Authorization': 'Bearer ' + token }
      })
        .then(r => { if (r.ok) return r.json(); throw new Error('not-authed'); })
        .then(profile => {
          const data = {
            name: profile.name || 'Officer',
            dept: profile.department || 'Ministry of Defence',
            role: profile.role || 'Procurement Officer',
            email: profile.email || ''
          };
          localStorage.setItem('onyx_officer', JSON.stringify(data));
          currentOfficer = `${data.name} (${data.dept})`;
          currentDept = data.dept;
          currentRole = data.role;
          const deptInput = document.getElementById('dept-input');
          if (deptInput) deptInput.value = data.dept;
          const officerDisplay = document.getElementById('officer-name-display');
          if (officerDisplay) officerDisplay.textContent = `${data.name} (${data.dept.replace('Ministry of ', '').replace(' / NIC', '')})`;
          alert(`Officer identity set from signed-in profile:\n\n${data.name}\n${data.role}\n${data.dept}`);
        })
        .catch(() => {
          alert('Signed-in session is invalid or expired. Please sign in again.');
          localStorage.removeItem('onyx_token');
          window.location.href = '/landing.html#auth';
        });
    }

    function setQueryMode(mode) {
      activeMode = mode;
      const btnProd = document.getElementById('btn-mode-product');
      const btnServ = document.getElementById('btn-mode-service');
      if (btnProd) btnProd.classList.toggle('active', mode === 'product');
      if (btnServ) btnServ.classList.toggle('active', mode === 'service');
      
      const prodFilters = document.getElementById('product-filters');
      const servFilters = document.getElementById('service-filters');
      if (prodFilters) prodFilters.style.display = mode === 'product' ? 'grid' : 'none';
      if (servFilters) servFilters.style.display = mode === 'service' ? 'grid' : 'none';
      
      const queryInput = document.getElementById('query-input');
      if (queryInput) {
        if (mode === 'service') {
          queryInput.placeholder = "Enter service title (e.g. Annual Maintenance Contract - Desktop Computer, Security Manpower Services)";
        } else {
          queryInput.placeholder = "Enter product name (e.g. Cisco Catalyst 9300, HP ProBook 450 G10, A4 Paper 75gsm, Radar Waveguide)";
        }
      }
    }

    function applyPreset(query, cat, mode, qty, dept, value, params) {
      setQueryMode(mode);
      const queryInput = document.getElementById('query-input');
      const catSelect = document.getElementById('cat-select');
      const qtyInput = document.getElementById('qty-input');
      const deptInput = document.getElementById('dept-input');
      const valueInput = document.getElementById('value-input');
      const paramsInput = document.getElementById('params-input');
      
      if (queryInput) queryInput.value = query;
      if (catSelect && cat) catSelect.value = cat;
      if (qtyInput && qty) qtyInput.value = qty;
      if (deptInput && dept) deptInput.value = dept;
      if (valueInput) valueInput.value = value || '';
      if (paramsInput) paramsInput.value = params || '';
      
      executeBenchmark();
    }

    function applyServicePreset(query, serviceType, duration, dept, location) {
      setQueryMode('service');
      const queryInput = document.getElementById('query-input');
      const servSelect = document.getElementById('service-type-select');
      const durInput = document.getElementById('service-duration-input');
      const deptInput = document.getElementById('dept-input');
      const locInput = document.getElementById('service-location-input');
      
      if (queryInput) queryInput.value = query;
      if (servSelect && serviceType) servSelect.value = serviceType;
      if (durInput && duration) durInput.value = duration;
      if (deptInput && dept) deptInput.value = dept;
      if (locInput && location) locInput.value = location;
      
      executeBenchmark();
    }

    function handleBenchmarkSubmit(e) {
      if (e) e.preventDefault();
      executeBenchmark();
    }

    async function executeBenchmark() {
      const queryInput = document.getElementById('query-input');
      const query = queryInput ? queryInput.value.trim() : '';
      if (!query) return;
      
      currentQuery = query;
      const deptInput = document.getElementById('dept-input');
      const dept = deptInput ? deptInput.value.trim() : currentDept;
      currentDept = dept;
      
      const stageSelect = document.getElementById(activeMode === 'product' ? 'stage-select' : 'service-stage-select');
      currentMilestone = stageSelect ? stageSelect.value : 'Stage 1: Admin Approval (A/A)';

      const btn = document.getElementById('btn-run-benchmark');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<svg class="icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg> Executing GFR Waterfall...';
      }
      
      const stepper = document.getElementById('waterfall-stepper');
      if (stepper) stepper.style.display = 'block';
      const resultsArea = document.getElementById('results-area');
      if (resultsArea) resultsArea.style.display = 'none';
      
      resetStepper();

      // Clear transient state boxes from any previous run
      const prevErrBox = document.getElementById('bench-error-box');
      if (prevErrBox) prevErrBox.style.display = 'none';
      const prevEmptyBox = document.getElementById('bench-empty-box');
      if (prevEmptyBox) prevEmptyBox.style.display = 'none';
      
      // Show skeleton loading state
      showResultsSkeleton();

      try {
        const catSelect = document.getElementById('cat-select');
        const qtyInput = document.getElementById('qty-input');
        const valueInput = document.getElementById('value-input');
        const paramsInput = document.getElementById('params-input');
        const locInput = document.getElementById('loc-input');
        const servSelect = document.getElementById('service-type-select');
        const durInput = document.getElementById('service-duration-input');
        const locInputSvc = document.getElementById('service-location-input');
        const scopeInput = document.getElementById('service-scope-input');

        const specs = parseGoldenParams(paramsInput ? paramsInput.value : '');
        
        const payload = {
          product_name: query,
          query_mode: activeMode,
          department: dept || null,
          category: activeMode === 'product' && catSelect ? (catSelect.value || null) : null,
          quantity: activeMode === 'product' && qtyInput ? (parseInt(qtyInput.value) || 1) : 1,
          estimated_value: activeMode === 'product' && valueInput && valueInput.value ? (parseFloat(valueInput.value) || null) : null,
          delivery_location: (activeMode === 'product' && locInput && locInput.value.trim()) ? locInput.value.trim()
                            : (activeMode === 'service' && locInputSvc && locInputSvc.value.trim() ? locInputSvc.value.trim() : null),
          service_type: activeMode === 'service' && servSelect ? servSelect.value : null,
          service_duration: activeMode === 'service' && durInput ? String(durInput.value) : null,
          service_location: activeMode === 'service' && locInputSvc ? locInputSvc.value : null,
          service_scope: activeMode === 'service' && scopeInput ? scopeInput.value : null,
          specs: activeMode === 'product' && Object.keys(specs).length ? specs : null
        };
        
        const headers = { 'Content-Type': 'application/json' };
        const token = localStorage.getItem('onyx_token');
        if (token) headers['Authorization'] = 'Bearer ' + token;
        
        const res = await fetch('/api/v1/benchmark', {
          method: 'POST',
          headers: headers,
          body: JSON.stringify(payload)
        });
        
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Server responded with status ${res.status}`);
        }
        
        const data = await res.json();
        lastBenchmarkData = data;
        
        updateStepperWithTrace(data);
        renderResults(data);
        renderThreshold(data);
        renderBaseProduct(data);
        renderFreight(data);
        renderDelegation(data);
        
      } catch (err) {
        console.error('Benchmark Error:', err);
        const errBox = document.getElementById('bench-error-box');
        const errMsg = document.getElementById('bench-error-msg');
        if (errBox && errMsg) {
          errMsg.textContent = err.message;
          errBox.style.display = 'block';
        } else {
          alert('Benchmark Request Failed: ' + err.message);
        }
        const emptyBox = document.getElementById('bench-empty-box');
        if (emptyBox) emptyBox.style.display = 'none';
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<svg class="icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> Run GFR 149(vii) Reasonability Benchmark';
        }
        if (resultsArea) resultsArea.style.display = 'block';
      }
    }

    function resetStepper() {
      for (let i = 0; i <= 4; i++) {
        const node = document.getElementById(`step-node-${i}`);
        if (node) node.className = 'step-node';
        const st = document.getElementById(`step-status-${i}`);
        if (st) st.textContent = 'Awaiting result...';
      }
      const sBadge = document.getElementById('stepper-status-badge');
      if (sBadge) {
        sBadge.textContent = 'Running statutory cascade…';
        sBadge.style.color = 'var(--primary)';
      }
    }

    function setStepState(tier, state, statusText) {
      const node = document.getElementById(`step-node-${tier}`);
      if (!node) return;
      node.className = `step-node ${state}`;
      const st = document.getElementById(`step-status-${tier}`);
      if (st) st.textContent = statusText;
    }

    function updateStepperWithTrace(data) {
      const resolvedTier = data.resolved_tier;
      const trace = data.tier_trace || {};
      
      for (let i = 0; i <= 4; i++) {
        const traceKey = `tier_${i}`;
        const outcome = trace[traceKey] || '';
        const outcomeLower = outcome.toLowerCase();
        
        if (i === resolvedTier) {
          setStepState(i, 'resolved', '✓ Resolved: Primary Result');
        } else if (i < resolvedTier) {
          setStepState(i, 'missed', outcomeLower.includes('no') ? '✗ No Record' : outcome);
        } else {
          setStepState(i, 'skipped', '⊘ Skipped (Precedence Met)');
        }
      }
      
      const sBadge = document.getElementById('stepper-status-badge');
      if (sBadge) {
        sBadge.textContent = `✓ Resolved at Tier ${resolvedTier}`;
        sBadge.style.color = 'var(--t0-color)';
      }
    }

    function renderThreshold(data) {
      const box = document.getElementById('threshold-banner');
      if (!box) return;
      const t = data.procurement_threshold;
      if (!t) { box.style.display = 'none'; return; }

      const tone = t.compliant ? 'compliant' : 'noncompliant';
      const quotesNote = t.mode === 'direct_purchase'
        ? 'competitive quotation not statutorily required'
        : `${t.quotes_obtained} / ${t.min_quotes_required} independent quote(s) gathered`;
      box.className = 'threshold-banner ' + tone;
      box.innerHTML = `
        <div class="threshold-icon">${t.compliant ? '&#10003;' : '&#9888;'}</div>
        <div class="threshold-body">
          <div class="threshold-title">Est. ${formatINR(t.value)} &rarr; <strong>${esc(t.mode_label)}</strong> <span class="threshold-rule">(${esc(t.rule)})</span></div>
          <div class="threshold-meta">${t.compliant ? 'Compliant' : 'Non-compliant'} &middot; ${esc(quotesNote)} &middot; ${esc(t.evidence_required)}</div>
          ${t.non_compliance ? `<div class="threshold-warn">${esc(t.non_compliance)}</div>` : ''}
        </div>`;
      box.style.display = 'flex';
    }

    function renderBaseProduct(data) {
      const box = document.getElementById('base-product-card');
      if (!box) return;
      const bp = data.base_product;
      if (!bp) { box.style.display = 'none'; return; }

      const primary = data.primary_result || {};
      const bench = primary.price != null ? Number(primary.price) : null;
      let html = `<strong style="color:#4338ca;">Canonical Base Product:</strong> <span style="font-weight:600;">${esc(bp.canonical_name)}</span>`;
      if (bp.match_score != null) {
        html += ` <span style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#64748b;">(identity match ${bp.match_score}%)</span>`;
      }
      html += '<div style="margin-top:4px;">';
      if (bp.prior_records > 0) {
        const deptLabel = bp.prior_departments && bp.prior_departments.length ? bp.prior_departments[0] : 'department';
        let delta = '';
        if (bench != null && bp.prior_median_price) {
          const d = Math.round((bench - bp.prior_median_price) / bp.prior_median_price * 100);
          const tone = Math.abs(d) <= 10 ? 'color:#047857;' : (d > 0 ? 'color:#b45309;' : 'color:#b91c1c;');
          delta = ` &middot; benchmark is <strong style="${tone}">${d >= 0 ? '+' : ''}${d}%</strong> vs prior median`;
        }
        html += `Recognized from <strong>${bp.prior_records} prior ${esc(deptLabel)} purchase record(s)</strong> &middot; prior median <strong>${formatINR(bp.prior_median_price)}</strong> (range ${formatINR(bp.prior_min)}&ndash;${formatINR(bp.prior_max)})${delta}`;
      } else {
        html += `No prior purchase records for this base product in the department &mdash; this benchmark establishes the reference price.`;
      }
      html += '</div>';
      box.innerHTML = html;
      box.style.display = 'block';
    }

    function renderFreight(data) {
      const box = document.getElementById('freight-card');
      if (!box) return;
      const f = data.freight;
      if (!f) { box.style.display = 'none'; return; }
      box.innerHTML = `
        <strong style="color:#15803d;">Landed Cost (Demo-Simulated Freight):</strong>
        <span style="font-weight:600;">${esc(f.delivery_location)}</span> &middot; ${esc(f.region_label)} (${f.freight_pct}% of goods value)<br>
        Goods (${f.quantity} × ${formatINR(f.goods_value / f.quantity)}) <strong>${formatINR(f.goods_value)}</strong>
        + Freight <strong>${formatINR(f.freight_amount)}</strong>
        = <strong>Landed Total ${formatINR(f.landed_total)}</strong>
        <div style="margin-top:6px;font-size:11.5px;opacity:0.85;">${esc(f.note)}</div>`;
      box.style.display = 'block';
    }

    function renderDelegation(data) {
      const card = document.getElementById('delegation-card');
      if (!card) return;
      if (!data || !data.search_id) { card.style.display = 'none'; return; }
      card.style.display = 'block';
      const chip = document.getElementById('delegation-status-chip');
      if (chip) {
        const open = lastDelegations ? lastDelegations.filter(d => d.status === 'open').length : 0;
        chip.textContent = open ? `${open} open review${open > 1 ? 's' : ''}` : 'No open reviews';
      }
      loadDelegationTrail(data.search_id);
    }

    let lastDelegations = [];
    let lastAudit = [];

    async function loadDelegationTrail(searchId) {
      try {
        const [dres, ares] = await Promise.all([
          fetch(`/api/v1/delegations?search_id=${encodeURIComponent(searchId)}`, {
            headers: { 'Authorization': 'Bearer ' + getToken() }
          }),
          fetch(`/api/v1/audit?search_id=${encodeURIComponent(searchId)}`, {
            headers: { 'Authorization': 'Bearer ' + getToken() }
          })
        ]);
        if (dres.ok) lastDelegations = await dres.json();
        if (ares.ok) lastAudit = await ares.json();
      } catch (e) {
        console.error('Delegation trail load failed:', e);
      }
      renderDelegationTrail();
    }

    function renderDelegationTrail() {
      const listEl = document.getElementById('delegation-list');
      const auditEl = document.getElementById('audit-log');
      const chip = document.getElementById('delegation-status-chip');

      if (chip) {
        const open = lastDelegations.filter(d => d.status === 'open').length;
        chip.textContent = open ? `${open} open review${open > 1 ? 's' : ''}` : 'No open reviews';
      }

      if (listEl) {
        if (!lastDelegations.length) {
          listEl.innerHTML = '<em style="color:#64748b;">No delegations yet for this benchmark.</em>';
        } else {
          listEl.innerHTML = lastDelegations.map(d => {
            const state = d.status === 'open'
              ? '<span style="color:#b45309;font-weight:600;">● OPEN</span>'
              : `<span style="color:#15803d;font-weight:600;">${d.decision === 'approved' ? '✓ APPROVED' : '✗ REJECTED'}</span>`;
            const resolveBtns = d.status === 'open'
              ? `<button type="button" class="btn-action btn-outline" style="padding:3px 10px;font-size:11.5px;" onclick="resolveDelegation('${d.id}','approved')">Approve</button>
                 <button type="button" class="btn-action btn-outline" style="padding:3px 10px;font-size:11.5px;" onclick="resolveDelegation('${d.id}','rejected')">Reject</button>`
              : '';
            return `
              <div style="display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-bottom:1px solid #f1f5f9;">
                <div style="flex:1;">
                  <strong>${esc(d.delegate_to_name)}</strong>
                  ${d.delegate_to_email ? `<span style="color:#64748b;"> &lt;${esc(d.delegate_to_email)}&gt;</span>` : ''}
                  <div style="color:#475569;font-size:12px;">${esc(d.note || 'Requested to review the benchmark price evidence')}</div>
                  <div style="color:#94a3b8;font-size:11px;">Delegated by ${esc(d.delegated_by_name || 'the benchmarking officer')} · ${new Date(d.created_at).toLocaleString()}</div>
                  ${d.decision_note ? `<div style="color:#475569;font-size:12px;">Review note: ${esc(d.decision_note)}</div>` : ''}
                </div>
                <div style="text-align:right;white-space:nowrap;">${state}<br>${resolveBtns}</div>
              </div>`;
          }).join('');
        }
      }

      if (auditEl) {
        if (!lastAudit.length) {
          auditEl.innerHTML = '<em style="color:#94a3b8;">No audit entries.</em>';
        } else {
          auditEl.innerHTML = '<strong style="font-size:11px;letter-spacing:0.5px;text-transform:uppercase;color:#64748b;">Audit Trail</strong>' +
            lastAudit.map(e => `
              <div style="display:flex;gap:8px;padding:3px 0;font-family:'JetBrains Mono',monospace;">
                <span style="color:#94a3b8;white-space:nowrap;">${new Date(e.created_at).toLocaleTimeString()}</span>
                <span style="color:#4338ca;">${esc(e.action)}</span>
                <span style="color:#64748b;flex:1;">${esc(e.actor_name || '—')}${e.note ? ' · ' + esc(e.note) : ''}</span>
              </div>`).join('');
        }
      }
    }

    async function delegateForReview() {
      const d = lastBenchmarkData;
      if (!d || !d.search_id) { alert('Run a benchmark first.'); return; }
      const nameEl = document.getElementById('del-name');
      const emailEl = document.getElementById('del-email');
      const noteEl = document.getElementById('del-note');
      const name = nameEl ? nameEl.value.trim() : '';
      if (!name) { alert('Enter the officer name to delegate to.'); return; }
      const res = await fetch('/api/v1/delegations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken() },
        body: JSON.stringify({
          search_id: d.search_id,
          delegate_to_name: name,
          delegate_to_email: (emailEl ? emailEl.value.trim() : '') || null,
          note: (noteEl ? noteEl.value.trim() : '') || null
        })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert('Delegation failed: ' + (err.detail || res.status));
        return;
      }
      if (nameEl) nameEl.value = '';
      if (emailEl) emailEl.value = '';
      if (noteEl) noteEl.value = '';
      loadDelegationTrail(d.search_id);
    }

    async function resolveDelegation(id, decision) {
      const note = window.prompt(decision === 'approved'
        ? 'Approval note (optional):'
        : 'Reason for rejection (optional):');
      if (note === null) return;
      const res = await fetch(`/api/v1/delegations/${id}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken() },
        body: JSON.stringify({ decision: decision, note: note || null })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert('Resolution failed: ' + (err.detail || res.status));
        return;
      }
      if (lastBenchmarkData) loadDelegationTrail(lastBenchmarkData.search_id);
    }

    function renderResults(data) {
      const resolvedTier = data.resolved_tier;
      const primary = data.primary_result || {};
      const manualReview = primary.price == null;

      // Hide skeleton, show results
      hideResultsSkeleton();
      
      // Clear transient state boxes on success
      const errBox = document.getElementById('bench-error-box');
      if (errBox) errBox.style.display = 'none';
      const emptyBox = document.getElementById('bench-empty-box');
      
      // "No evidence" only when the engine truly returned nothing; the manual-review
      // fallback is surfaced by the dedicated LPC panel instead.
      const noEvidence = !manualReview && !data.primary_result && (!data.all_results || !data.all_results.length);
      if (noEvidence && emptyBox) {
        emptyBox.style.display = 'block';
      } else if (emptyBox) {
        emptyBox.style.display = 'none';
      }
      
      // Apply tier-specific styling to primary card
      const primaryCard = document.querySelector('.primary-card');
      if (primaryCard) {
        primaryCard.className = 'card primary-card resolved-tier-' + resolvedTier;
      }
      
      const tierBadge = document.getElementById('tier-badge-container');
      if (tierBadge) {
        tierBadge.innerHTML = `<span class="tier-resolution-banner badge-tier-${resolvedTier}">Tier ${resolvedTier}: ${escapeHtml(data.tier_label)}</span>`;
      }
      
      // Animate price count-up
      const resPrice = document.getElementById('res-price');
      if (resPrice) {
        if (manualReview) {
          resPrice.textContent = '—';
          resPrice.classList.add('price-unspecified');
        } else {
          resPrice.classList.remove('price-unspecified');
          animatePriceCount(resPrice, primary.price || 0);
        }
      }
      
      const resRange = document.getElementById('res-range');
      if (resRange) {
        if (manualReview) {
          resRange.textContent = 'No automated price resolved — LPC negotiation required';
        } else if (primary.price_range_low && primary.price_range_high) {
          resRange.textContent = `Standard Range: ${formatINR(primary.price_range_low)} – ${formatINR(primary.price_range_high)}`;
        } else {
          resRange.textContent = `Statutory Reasonability Baseline (Per Unit)`;
        }
      }
      
      const conf = primary.confidence || 'LOW';
      const confBadge = document.getElementById('res-conf-badge');
      if (confBadge) confBadge.innerHTML = `<span class="conf-badge conf-${conf}">${conf} Confidence</span>`;
      
      const srcBadge = document.getElementById('res-source-badge');
      if (srcBadge) srcBadge.textContent = `Source: ${primary.source_name || 'Government System'}`;
      
      const modeBadge = document.getElementById('res-mode-badge');
      if (modeBadge) modeBadge.textContent = `Mode: ${data.query_mode ? data.query_mode.toUpperCase() : 'PRODUCT'}`;
      
      const mileBadge = document.getElementById('res-milestone-badge');
      if (mileBadge) mileBadge.textContent = `Milestone: ${currentMilestone}`;

      const demoBadgeEl = document.getElementById('res-demo-badge');
      const demoWarning = document.getElementById('demo-warning');
      const isDemo = primary.is_demo_data === true || data.any_demo_data === true;
      if (demoBadgeEl) {
        demoBadgeEl.innerHTML = isDemo
          ? '<span class="demo-badge"><svg class="icon" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align:-1px;margin-right:3px;"><path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>DEMO DATA</span>'
          : '<span class="real-badge"><svg class="icon" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align:-1px;margin-right:3px;"><path d="M20 6L9 17l-5-5"/></svg>REAL SOURCE</span>';
      }
      if (demoWarning) demoWarning.style.display = isDemo ? 'block' : 'none';

      // Certificate is blocked until a price resolves; demo-sourced reports are watermarked.
      const certBtn = document.getElementById('btn-open-cert');
      if (certBtn) {
        if (manualReview) {
          certBtn.disabled = true;
          certBtn.style.opacity = '0.45';
          certBtn.style.cursor = 'not-allowed';
          certBtn.title = 'Certificate unavailable — no automated price resolved. Complete LPC review first.';
        } else {
          certBtn.disabled = false;
          certBtn.style.opacity = '';
          certBtn.style.cursor = '';
          certBtn.title = isDemo ? 'Report will be watermarked DEMO MODE' : '';
        }
      }
      const rationaleBox = document.getElementById('res-rationale');
      if (rationaleBox) rationaleBox.textContent = primary.rationale || 'Price verified through GFR statutory precedence cascade.';

      const lpcBox = document.getElementById('lpc-review-box');
      const lpcMsg = document.getElementById('lpc-review-msg');
      const lpcRef = document.getElementById('lpc-review-ref');
      if (lpcBox && lpcMsg && lpcRef) {
        if (manualReview) {
          lpcBox.style.display = 'block';
          lpcMsg.textContent = primary.rationale || 'Insufficient data across all statutory tiers.';
          lpcRef.textContent = 'Referral: ' + (primary.evidence_reference || 'Local Purchase Committee (GFR Rule 155)');
        } else {
          lpcBox.style.display = 'none';
        }
      }
      
      const dutyCard = document.getElementById('duty-breakdown-card');
      if (dutyCard) {
        if (resolvedTier === 4 && primary.price) {
          dutyCard.style.display = 'block';
          const base = primary.price / 1.42;
          const dBase = document.getElementById('duty-base');
          if (dBase) dBase.textContent = formatINR(base);
          const dTotal = document.getElementById('duty-total');
          if (dTotal) dTotal.textContent = formatINR(primary.price);
        } else {
          dutyCard.style.display = 'none';
        }
      }
      
      const traceList = document.getElementById('trace-list');
      if (traceList) {
        traceList.innerHTML = '';
        if (data.tier_trace) {
          Object.entries(data.tier_trace).forEach(([key, val]) => {
            const tierNum = key.replace('tier_', '');
            const isResolved = parseInt(tierNum) === resolvedTier;
            const valLower = String(val).toLowerCase();
            
            let iconClass = 'skip';
            let iconSym = '⊘';
            if (isResolved || valLower.includes('found')) {
              iconClass = 'pass';
              iconSym = '✓';
            } else if (valLower.includes('no') || valLower.includes('failed') || valLower.includes('insufficient')) {
              iconClass = 'fail';
              iconSym = '✗';
            }
            
            const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            traceList.innerHTML += `
              <li class="trace-item">
                <span class="trace-icon ${iconClass}">${iconSym}</span>
                <div>
                  <strong>${escapeHtml(label)}:</strong> 
                  <span>${escapeHtml(val)}</span>
                </div>
              </li>
            `;
          });
        }
      }
      
      const stats = data.statistics || {};
      const sMin = document.getElementById('stat-min');
      if (sMin) sMin.textContent = formatINR(stats.min);
      const sAvg = document.getElementById('stat-avg');
      if (sAvg) sAvg.textContent = formatINR(stats.avg);
      const sMed = document.getElementById('stat-median');
      if (sMed) sMed.textContent = formatINR(stats.median);
      const sMax = document.getElementById('stat-max');
      if (sMax) sMax.textContent = formatINR(stats.max);
      const sCount = document.getElementById('stat-count');
      if (sCount) sCount.textContent = stats.count || (data.all_results ? data.all_results.length : 0);

      // ── L1 competitive bid + reasonableness band ──
      const sL1 = document.getElementById('stat-l1');
      if (sL1) sL1.textContent = stats.l1 != null ? formatINR(stats.l1) : '—';
      const sL1Sub = document.getElementById('stat-l1-sub');
      if (sL1Sub) {
        if (stats.l1 != null) {
          const src = stats.l1_source ? ' · ' + stats.l1_source : '';
          const poolNote = stats.l1_valid
            ? ' · Valid pool ✓'
            : (stats.competitive_pool ? ' · Pool < 3 quotes' : '');
          sL1Sub.textContent = (stats.l1_vendor || 'L1') + src + poolNote;
        } else {
          sL1Sub.textContent = '';
        }
      }
      const sBand = document.getElementById('stat-band');
      if (sBand) {
        sBand.textContent = (stats.band_low != null && stats.band_high != null)
          ? `${formatINR(stats.band_low)} – ${formatINR(stats.band_high)}`
          : '—';
      }
      const sBandSub = document.getElementById('stat-band-sub');
      if (sBandSub) {
        if (stats.primary_price != null && stats.band_low != null) {
          sBandSub.textContent = stats.within_band
            ? 'Primary within band ✓'
            : 'Primary OUTSIDE band ⚠ review';
        } else {
          sBandSub.textContent = '';
        }
      }

      // ── Outlier / quality advisory on the primary price ──
      const qwBox = document.getElementById('quality-warning');
      const qwMsg = document.getElementById('quality-warning-msg');
      if (qwBox && qwMsg) {
        let advisory = '';
        if (!manualReview && primary.price) {
          const statsCount = stats.count || 0;
          if (statsCount >= 3 && stats.median) {
            const devPct = ((primary.price - stats.median) / stats.median) * 100;
            if (Math.abs(devPct) >= 25) {
              advisory = `Primary price is ${Math.abs(devPct).toFixed(0)}% ${devPct > 0 ? 'above' : 'below'} the market median (${formatINR(stats.median)}). Cross-check quality, warranty and vendor terms before acceptance.`;
            }
          }
          if (!advisory && String(primary.reliability || '').toUpperCase() === 'LOW') {
            advisory = 'Primary source flagged as a market outlier (LOW reliability). Verify reasonableness against a wider sample before accepting.';
          }
        }
        qwBox.style.display = advisory ? 'block' : 'none';
        qwMsg.textContent = advisory;
      }
      
      allTableData = data.all_results || [];
      goldenParams = data.specs && typeof data.specs === 'object' ? Object.entries(data.specs) : [];
      renderGoldenParams();
      applyTableFilters();
      showEvidenceChrome();
    }

    function parseGoldenParams(raw) {
      const out = {};
      if (!raw) return out;
      const parts = String(raw).split(/[,;]/).map(s => s.trim()).filter(Boolean);
      parts.forEach((part, i) => {
        const idx = part.indexOf(':');
        if (idx > 0) {
          out[part.slice(0, idx).trim()] = part.slice(idx + 1).trim();
        } else {
          out['param' + (i + 1)] = part;
        }
      });
      return out;
    }

    function rowParamMatches(row) {
      if (!goldenParams.length) return false;
      const hay = String((row.source_name || '') + ' ' + (row.rationale || '') + ' ' + (row.evidence_reference || '')).toLowerCase();
      return goldenParams.some(([, val]) => {
        if (!val) return false;
        const tokens = String(val).toLowerCase().split(/[\s/,-]+/).filter(t => t.length > 2);
        return tokens.some(t => hay.includes(t));
      });
    }

    function renderGoldenParams() {
      const strip = document.getElementById('golden-params-strip');
      if (!strip) return;
      if (!goldenParams.length) { strip.style.display = 'none'; strip.innerHTML = ''; return; }
      const chips = goldenParams.map(([k, v]) =>
        `<span style="display:inline-block;background:#eef2ff;color:#4338ca;border:1px solid #c7d2fe;border-radius:6px;padding:2px 8px;margin:2px 4px 2px 0;font-size:11.5px;font-family:'JetBrains Mono',monospace;"><strong>${esc(k)}:</strong> ${esc(v)}</span>`
      ).join('');
      strip.innerHTML = `<strong style="margin-right:6px;">Golden Parameters</strong> — the configured baseline the benchmarked price must satisfy: ${chips}`;
      strip.style.display = 'block';
    }

    function showEvidenceChrome() {
      const bar = document.getElementById('facet-tier');
      if (bar && bar.closest('.facets-bar')) bar.closest('.facets-bar').style.display = 'flex';
    }

    function applyTableFilters() {
      const fTier = document.getElementById('facet-tier');
      const fOrigin = document.getElementById('facet-origin');
      const fMin = document.getElementById('facet-min');
      const fMax = document.getElementById('facet-max');
      const fMatch = document.getElementById('facet-match');
      const tier = fTier ? fTier.value : '';
      const origin = fOrigin ? fOrigin.value : '';
      const min = fMin && fMin.value !== '' ? parseFloat(fMin.value) : null;
      const max = fMax && fMax.value !== '' ? parseFloat(fMax.value) : null;
      const onlyMatch = fMatch ? fMatch.checked : false;

      tableData = allTableData.filter(row => {
        if (tier !== '' && String(row.tier) !== tier) return false;
        if (origin === 'demo' && row.is_demo_data !== true) return false;
        if (origin === 'real' && row.is_demo_data === true) return false;
        if (min != null && (row.price == null || row.price < min)) return false;
        if (max != null && (row.price == null || row.price > max)) return false;
        if (onlyMatch && !rowParamMatches(row)) return false;
        return true;
      });

      const count = document.getElementById('facet-count');
      if (count) count.textContent = tableData.length + ' / ' + allTableData.length + ' row(s)';
      renderTable();
    }

    function bindFacetControls() {
      ['facet-tier', 'facet-origin', 'facet-min', 'facet-max', 'facet-match'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', applyTableFilters);
      });
      const clear = document.getElementById('facet-clear');
      if (clear) clear.addEventListener('click', () => {
        const ids = { 'facet-tier': '', 'facet-origin': '', 'facet-min': '', 'facet-max': '' };
        for (const [id, val] of Object.entries(ids)) {
          const el = document.getElementById(id);
          if (el) el.value = val;
        }
        const fMatch = document.getElementById('facet-match');
        if (fMatch) fMatch.checked = false;
        applyTableFilters();
      });
    }

    function renderTable() {
      const tbody = document.getElementById('results-tbody');
      if (!tbody) return;
      tbody.innerHTML = '';
      
      if (!tableData.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#64748b;">No secondary price points recorded.</td></tr>';
        return;
      }
      
      const sorted = [...tableData].sort((a, b) => {
        let valA = a[sortCol];
        let valB = b[sortCol];
        if (sortCol === 'price' || sortCol === 'tier') {
          valA = parseFloat(valA) || 0;
          valB = parseFloat(valB) || 0;
        } else {
          valA = String(valA || '').toLowerCase();
          valB = String(valB || '').toLowerCase();
        }
        if (valA < valB) return sortAsc ? -1 : 1;
        if (valA > valB) return sortAsc ? 1 : -1;
        return 0;
      });
      
      sorted.forEach(row => {
        const tr = document.createElement('tr');
        const conf = row.confidence || 'LOW';
        const linkHtml = row.evidence_url 
          ? `<a href="${escapeHtml(row.evidence_url)}" target="_blank" class="source-link"><svg class="icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><path d="M15 3h6v6"/><path d="M10 14L21 3"/></svg> View Source</a>`
          : (row.evidence_reference
              ? `<span style="color:#64748b;font-size:12px;font-family:'JetBrains Mono',monospace;line-height:1.4;">${escapeHtml(row.evidence_reference)}</span>`
              : `<span style="color:#94a3b8;font-size:12px;">Internal Record</span>`);
        
        let originBadge = '<span style="font-weight:600;">T0 · Notified</span>';
        if (row.tier === 1) originBadge = '<span style="font-weight:600;">T1 · GeM BA</span>';
        else if (row.tier === 2) originBadge = '<span style="font-weight:600;">T2 · Dept PO</span>';
        else if (row.tier === 3) originBadge = '<span style="font-weight:600;">T3 · Market</span>';
        else if (row.tier === 4) originBadge = '<span style="font-weight:600;">T4 · Estimator</span>';
        
        const rowDemoBadge = row.is_demo_data === true
          ? ' <span class="demo-badge" style="font-size:10px;">DEMO</span>'
          : ' <span class="real-badge" style="font-size:10px;">REAL</span>';

        const isMatch = goldenParams.length > 0 && rowParamMatches(row);
        const matchTag = isMatch
          ? ' <span style="background:#ecfdf5;color:#047857;border:1px solid #6ee7b7;border-radius:6px;padding:1px 6px;font-size:10px;font-weight:600;white-space:nowrap;">&#10003; param match</span>'
          : (goldenParams.length > 0
              ? ' <span style="background:#f8fafc;color:#94a3b8;border:1px solid #e2e8f0;border-radius:6px;padding:1px 6px;font-size:10px;font-weight:600;white-space:nowrap;">spec n/a</span>'
              : '');

        tr.innerHTML = `
          <td><span class="step-tag" style="background:#f1f5f9;padding:2px 6px;border-radius:4px;">Tier ${escapeHtml(row.tier)}</span></td>
          <td>
            <div class="source-cell">
              <strong>${escapeHtml(row.source_name || 'System Record')}</strong>
              <span style="font-size:11px;color:#64748b;">${originBadge}${rowDemoBadge}${matchTag}</span>
            </div>
          </td>
          <td style="font-family:'JetBrains Mono';font-weight:700;">${row.price == null ? '—' : formatINR(row.price)}</td>
          <td><span class="conf-badge conf-${conf}">${conf}</span></td>
          <td>${escapeHtml(row.reliability || 'MEDIUM')}</td>
          <td>${linkHtml}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function bindTableSort() {
      document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
          const col = th.getAttribute('data-sort');
          if (sortCol === col) sortAsc = !sortAsc;
          else { sortCol = col; sortAsc = true; }
          renderTable();
        });
      });
    }

    function bindExportButtons() {
      const btnHtml = document.getElementById('btn-download-html');
      if (btnHtml) {
        btnHtml.addEventListener('click', () => {
          downloadReport('html');
        });
      }

      const btnPdf = document.getElementById('btn-download-pdf');
      if (btnPdf) {
        btnPdf.addEventListener('click', () => {
          downloadReport('pdf');
        });
      }
    }

    async function downloadReport(fmt) {
      if (!lastBenchmarkData || !lastBenchmarkData.search_id) {
        alert('Run a benchmark first, then export the report.');
        return;
      }
      const btn = document.getElementById(fmt === 'html' ? 'btn-download-html' : 'btn-download-pdf');
      const originalHTML = btn ? btn.innerHTML : '';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<svg class="icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg> Generating ' + fmt.toUpperCase() + '...';
      }
      const payload = {
        search_id: lastBenchmarkData.search_id,
        department_name: currentDept,
        signatory_name: currentOfficer.split('(')[0].trim(),
        output_format: fmt
      };
      const headers = { 'Content-Type': 'application/json' };
      const token = localStorage.getItem('onyx_token');
      if (token) headers['Authorization'] = 'Bearer ' + token;
      try {
        const res = await fetch('/api/v1/reports/generate', {
          method: 'POST',
          headers: headers,
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Server responded with status ${res.status}`);
        }
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        const safe = currentQuery.replace(/[^a-zA-Z0-9]+/g, '_').slice(0, 20);
        a.download = `benchmark_report_${safe}.${fmt}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(blobUrl);
      } catch (err) {
        alert('Report download failed: ' + err.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = originalHTML;
        }
      }
    }

    function openCertModal() {
      if (!lastBenchmarkData) return;
      
      const d = lastBenchmarkData;
      const primary = d.primary_result || {};
      
      const isDemo = primary.is_demo_data === true || d.any_demo_data === true;

      const certDemoBanner = document.getElementById('cert-demo-banner');
      if (certDemoBanner) certDemoBanner.style.display = isDemo ? 'block' : 'none';

      const cId = document.getElementById('cert-id');
      if (cId) cId.textContent = d.search_id ? `ONX-${d.search_id.slice(0, 8).toUpperCase()}` : 'ONX-PENDING';
      const cDate = document.getElementById('cert-date');
      if (cDate) cDate.textContent = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
      const cItem = document.getElementById('cert-item');
      if (cItem) cItem.textContent = currentQuery;
      const cDept = document.getElementById('cert-dept');
      if (cDept) cDept.textContent = currentDept || 'Ministry of Defence';
      const cMile = document.getElementById('cert-milestone');
      if (cMile) cMile.textContent = currentMilestone;
      const cOfficer = document.getElementById('cert-officer');
      if (cOfficer) cOfficer.textContent = currentOfficer;
      const cSignOfficer = document.getElementById('cert-sign-officer');
      if (cSignOfficer) cSignOfficer.textContent = currentOfficer.split(' (')[0];
      const cSignRole = document.getElementById('cert-sign-role');
      if (cSignRole) cSignRole.textContent = `[ ${currentRole}, ${currentDept} ]`;
      const cSignAuth = document.getElementById('cert-sign-auth');
      if (cSignAuth) cSignAuth.textContent = 'Approving Authority (to be signed after verification)';

      const cPrice = document.getElementById('cert-price');
      if (cPrice) cPrice.textContent = formatINR(primary.price);
      const cTier = document.getElementById('cert-tier-label');
      if (cTier) cTier.textContent = `Tier ${d.resolved_tier}: ${d.tier_label}`;

      const cL1Band = document.getElementById('cert-l1-band');
      if (cL1Band) {
        const st = d.statistics || {};
        let txt = '';
        if (st.l1 != null) {
          txt += `L1 (Lowest-1) Competitive Bid: ${formatINR(st.l1)}`;
          if (st.l1_source) txt += ` — ${st.l1_source}`;
          txt += ` · Competitive Pool: ${st.competitive_pool ?? 0} source(s)`;
        }
        if (st.median != null && st.band_low != null) {
          txt += ` · Reasonableness Band: ${formatINR(st.band_low)} – ${formatINR(st.band_high)} (median ±25%)`;
          if (st.within_band !== undefined) {
            txt += st.within_band
              ? ' · Primary: WITHIN band'
              : ' · Primary: OUTSIDE band — justification required';
          }
        }
        cL1Band.textContent = txt;
      }

      const cGolden = document.getElementById('cert-golden-params');
      if (cGolden) {
        const sp = (d.specs && typeof d.specs === 'object') ? Object.entries(d.specs) : [];
        if (sp.length) {
          cGolden.textContent = 'Golden Parameters: ' + sp.map(([k, v]) => `${k}: ${v}`).join(' | ');
          cGolden.style.display = 'block';
        } else {
          cGolden.style.display = 'none';
        }
      }

      const cFreight = document.getElementById('cert-freight');
      if (cFreight) {
        const f = d.freight;
        if (f) {
          cFreight.textContent = `Landed Cost (${f.delivery_location}): Goods ${formatINR(f.goods_value)} + Freight ${formatINR(f.freight_amount)} = ${formatINR(f.landed_total)} (demo-simulated, ${f.freight_pct}%)`;
          cFreight.style.display = 'block';
        } else {
          cFreight.style.display = 'none';
        }
      }
      
      const traceBody = document.getElementById('cert-trace-body');
      if (traceBody) {
        traceBody.innerHTML = '';
        
        const tierTitles = [
          'Tier 0: DGS&D / Ministry Notified Rates',
          'Tier 1: GeM Business Analytics & LPP',
          'Tier 2: Department Purchase Order Ingestion',
          'Tier 3: Multi-Source Market Survey',
          'Tier 4: Non-Standard / Landed Cost Estimator'
        ];
        
        for (let i = 0; i <= 4; i++) {
          const traceKey = `tier_${i}`;
          const outcome = (d.tier_trace && d.tier_trace[traceKey]) || (i === d.resolved_tier ? 'Resolved' : 'Skipped');
          const isResolved = i === d.resolved_tier;
          
          traceBody.innerHTML += `
            <tr style="${isResolved ? 'background:#f0fdf4;font-weight:bold;' : ''}">
              <td>${tierTitles[i]}</td>
              <td>${isResolved ? escapeHtml(primary.source_name) : 'Statutory Registry'}</td>
              <td>${escapeHtml(outcome)}</td>
            </tr>
          `;
        }
      }
      
      const modal = document.getElementById('cert-modal');
      if (modal) modal.style.display = 'flex';
    }

    function closeCertModal() {
      const modal = document.getElementById('cert-modal');
      if (modal) modal.style.display = 'none';
    }

    // Skeleton loading states
    function showResultsSkeleton() {
      const resultsArea = document.getElementById('results-area');
      const stepper = document.getElementById('waterfall-stepper');
      if (resultsArea) {
        resultsArea.style.display = 'block';
        resultsArea.innerHTML = `
          <div class="results-skeleton" id="results-skeleton">
            <div class="card primary-card skeleton-card">
              <div class="skeleton skeleton-title"></div>
              <div class="skeleton skeleton-badge"></div>
              <div class="skeleton skeleton-price"></div>
              <div class="skeleton skeleton-badge"></div>
              <div class="skeleton skeleton-badge"></div>
              <div class="skeleton skeleton-text"></div>
              <div class="skeleton skeleton-text"></div>
            </div>
            <div class="card skeleton-card">
              <div class="skeleton skeleton-title"></div>
              <ul class="trace-list">
                <li class="skeleton skeleton-text" style="height:2rem;width:100%;margin-bottom:0.5rem;"></li>
                <li class="skeleton skeleton-text" style="height:2rem;width:100%;margin-bottom:0.5rem;"></li>
                <li class="skeleton skeleton-text" style="height:2rem;width:100%;margin-bottom:0.5rem;"></li>
                <li class="skeleton skeleton-text" style="height:2rem;width:100%;margin-bottom:0.5rem;"></li>
                <li class="skeleton skeleton-text" style="height:2rem;width:100%;"></li>
              </ul>
            </div>
            <div class="stats-row">
              <div class="stat-card skeleton-card"><div class="skeleton skeleton-price"></div><div class="skeleton skeleton-text"></div></div>
              <div class="stat-card skeleton-card"><div class="skeleton skeleton-price"></div><div class="skeleton skeleton-text"></div></div>
              <div class="stat-card skeleton-card"><div class="skeleton skeleton-price"></div><div class="skeleton skeleton-text"></div></div>
              <div class="stat-card skeleton-card"><div class="skeleton skeleton-price"></div><div class="skeleton skeleton-text"></div></div>
              <div class="stat-card skeleton-card"><div class="skeleton skeleton-price"></div><div class="skeleton skeleton-text"></div></div>
            </div>
            <div class="card skeleton-card">
              <div class="skeleton skeleton-title"></div>
              <div class="table-container">
                <table><tbody>
                  <tr><td class="skeleton skeleton-text" style="height:1.5rem;"></td><td class="skeleton skeleton-text" style="height:1.5rem;"></td><td class="skeleton skeleton-text" style="height:1.5rem;"></td><td class="skeleton skeleton-text" style="height:1.5rem;"></td><td class="skeleton skeleton-text" style="height:1.5rem;"></td><td class="skeleton skeleton-text" style="height:1.5rem;"></td></tr>
                  <tr><td class="skeleton skeleton-text" style="height:1.5rem;"></td><td class="skeleton skeleton-text" style="height:1.5rem;"></td><td class="skeleton skeleton-text" style="height:1.5rem;"></td><td class="skeleton skeleton-text" style="height:1.5rem;"></td><td class="skeleton skeleton-text" style="height:1.5rem;"></td><td class="skeleton skeleton-text" style="height:1.5rem;"></td></tr>
                </tbody></table>
              </div>
            </div>
            <div class="action-bar">
              <button class="btn-action btn-cert-preview" disabled style="opacity:0.5;"><span class="skeleton skeleton-badge"></span></button>
              <button class="btn-action btn-outline" disabled style="opacity:0.5;"><span class="skeleton skeleton-badge"></span></button>
              <button class="btn-action btn-outline" disabled style="opacity:0.5;"><span class="skeleton skeleton-badge"></span></button>
            </div>
        `;
      }
    }
    
    function hideResultsSkeleton() {
      const resultsArea = document.getElementById('results-area');
      const skeleton = document.getElementById('results-skeleton');
      if (skeleton) skeleton.remove();
      // Restore the real result markup the skeleton had replaced, then rebind
      // the listeners that were lost with the old DOM nodes.
      if (resultsArea && resultsAreaTemplate && !document.getElementById('res-price')) {
        resultsArea.innerHTML = resultsAreaTemplate;
        bindTableSort();
        bindExportButtons();
        bindFacetControls();
      }
    }

    // Price count-up animation
    function animatePriceCount(el, targetPrice) {
      if (!el) return;
      const duration = 800;
      const startTime = performance.now();
      const startPrice = 0;
      
      function animate(now) {
        const progress = Math.min((now - startTime) / duration, 1);
        // Ease-out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(startPrice + (targetPrice - startPrice) * eased);
        el.textContent = formatINR(current);
        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          el.classList.remove('counting');
        }
      }
      el.classList.add('counting');
      requestAnimationFrame(animate);
    }

    // Initialize session
    (async function initSession() {
      bindTableSort();
      bindExportButtons();
      bindFacetControls();
      const officer = await ensureAuth();
      if (officer) {
        currentOfficer = `${officer.name} (${officer.dept})`;
        currentDept = officer.dept;
        currentRole = officer.role;
        const deptInput = document.getElementById('dept-input');
        if (deptInput) deptInput.value = officer.dept;
        const officerDisplay = document.getElementById('officer-name-display');
        if (officerDisplay) officerDisplay.textContent = `${officer.name} (${officer.dept.replace('Ministry of ', '').replace(' / NIC', '')})`;
      }
      loadOfficerSession();
    })();
  