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
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
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
