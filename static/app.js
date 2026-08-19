/* Onyx shared application helpers.
 *
 * Loaded on every page before each page's inline script. Keeps the common
 * utilities (formatting, escaping, auth headers) in one place instead of
 * duplicating them per page.
 */

/* Format a number as Indian Rupees (₹1,23,456.00). */
function formatINR(val) {
  if (val === null || val === undefined || isNaN(val)) return 'N/A';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2
  }).format(val);
}

/* Escape a string for safe insertion into HTML. */
function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&')
    .replace(/</g, '<')
    .replace(/>/g, '>')
    .replace(/"/g, '"')
    .replace(/'/g, '&#039;');
}

/* Alias kept for pages that used `esc`. */
function esc(str) {
  return escapeHtml(str);
}

/* Build fetch headers, attaching the stored JWT when present. */
function authHeaders(extra = {}) {
  const headers = { ...extra };
  const token = localStorage.getItem('onyx_token');
  if (token) headers['Authorization'] = 'Bearer ' + token;
  return headers;
}

/* Read the cached officer identity object, or null. */
function getCachedOfficer() {
  try {
    const raw = localStorage.getItem('onyx_officer');
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

/* Price count-up animation for hero price displays. */
function animatePriceCount(el, targetPrice, duration = 800) {
  if (!el) return;
  const startTime = performance.now();
  const startPrice = 0;
  
  function animate(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.round(startPrice + (targetPrice - startPrice) * eased);
    el.textContent = formatINR(current);
    if (progress < 1) requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
}

/* Ensure a valid JWT session exists before protected API calls. */
async function ensureAuth() {
  const token = localStorage.getItem('onyx_token');
  if (token) {
    try {
      const res = await fetch('/auth/me', {
        headers: { 'Authorization': 'Bearer ' + token }
      });
      if (res.ok) {
        const profile = await res.json();
        const officer = {
          name: profile.name,
          dept: profile.department || 'Ministry of Defence',
          role: profile.role || 'Procurement Officer',
          email: profile.email || ''
        };
        localStorage.setItem('onyx_officer', JSON.stringify(officer));
        return officer;
      }
    } catch (e) {
      // Network error — fall through to demo-login attempt below.
    }
    localStorage.removeItem('onyx_token');
  }

  try {
    const res = await fetch('/auth/demo-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Shri R. K. Sharma',
        email: 'r.sharma@mod.gov.in',
        department: 'Ministry of Defence'
      })
    });
    if (!res.ok) return null;
    const body = await res.json();
    localStorage.setItem('onyx_token', body.access_token);
    const officer = {
      name: 'Shri R. K. Sharma',
      dept: 'Ministry of Defence',
      role: 'Indenting Officer',
      email: 'r.sharma@mod.gov.in'
    };
    localStorage.setItem('onyx_officer', JSON.stringify(officer));
    return officer;
  } catch (e) {
    return null;
  }
}
