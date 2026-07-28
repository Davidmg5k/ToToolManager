// ToToolManager - Core frontend utilities
// Loaded on every page. Feature-specific code (CRUD tables, chat) lives in
// its own file and reuses the helpers defined here instead of redefining them.

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        setupHTMXErrorHandling();
        highlightActiveNav();
        updateFooterYear();
        if (document.getElementById('stat-users')) loadDashboardStats();
    });

    // ---------------------------------------------------------------------
    // HTMX-wide error handling
    // ---------------------------------------------------------------------
    function setupHTMXErrorHandling() {
        document.body.addEventListener('htmx:responseError', function (e) {
            var xhr = e.detail.xhr;
            var message = 'Something went wrong. Please try again.';
            try {
                var data = JSON.parse(xhr.responseText);
                message = data.detail || data.error || message;
            } catch (ex) { /* non-JSON error body, keep default */ }
            showErrorToast(message);
        });

        document.body.addEventListener('htmx:sendError', function () {
            showErrorToast('Network error. Check your connection and try again.');
        });
    }

    // ---------------------------------------------------------------------
    // Active nav / sidebar link highlighting, based on the current path
    // rather than a hardcoded class, so it stays correct on every page.
    // ---------------------------------------------------------------------
    function highlightActiveNav() {
        var path = window.location.pathname;
        document.querySelectorAll('[data-nav-link]').forEach(function (link) {
            var href = link.getAttribute('href');
            var isActive = href === '/' ? path === '/' : path.indexOf(href) === 0;
            link.classList.toggle('nav-link-active', isActive);
            link.classList.toggle('nav-link-inactive', !isActive);
            if (isActive) link.setAttribute('aria-current', 'page');
            else link.removeAttribute('aria-current');
        });
    }

    // ---------------------------------------------------------------------
    // Footer copyright year - only present on public (non-admin) pages.
    // ---------------------------------------------------------------------
    function updateFooterYear() {
        var el = document.getElementById('footer-year');
        if (el) el.textContent = new Date().getFullYear();
    }

    // ---------------------------------------------------------------------
    // Toasts
    // ---------------------------------------------------------------------
    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    function buildToast(message, variant) {
        var palette = {
            error: { bg: 'bg-red-600', icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>' },
            success: { bg: 'bg-emerald-600', icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>' },
            info: { bg: 'bg-gray-800', icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>' },
        }[variant] || palette_default();
        function palette_default() { return { bg: 'bg-gray-800', icon: '' }; }

        var toast = document.createElement('div');
        toast.className = palette.bg + ' pointer-events-auto text-white pl-3 pr-4 py-3 rounded-lg shadow-lg text-sm font-medium opacity-0 translate-y-2 transition-all duration-300 flex items-start gap-2 max-w-sm';
        toast.setAttribute('role', variant === 'error' ? 'alert' : 'status');
        toast.innerHTML =
            '<svg class="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">' + palette.icon + '</svg>' +
            '<span class="leading-snug">' + escapeHtml(message) + '</span>';
        return toast;
    }

    function pushToast(container, toast, duration) {
        container.appendChild(toast);
        requestAnimationFrame(function () {
            toast.classList.remove('opacity-0', 'translate-y-2');
        });
        setTimeout(function () {
            toast.classList.add('opacity-0', 'translate-y-2');
            setTimeout(function () { toast.remove(); }, 300);
        }, duration);
    }

    window.showErrorToast = function (message) {
        var container = document.getElementById('error-toast-container');
        if (!container) return;
        pushToast(container, buildToast(message, 'error'), 5000);
    };

    window.showToast = function (message, type) {
        var container = document.getElementById('toast-container');
        if (!container) return;
        pushToast(container, buildToast(message, type === 'error' ? 'error' : (type || 'success')), 3000);
    };

    window.escapeHtml = escapeHtml;

    // ---------------------------------------------------------------------
    // Generic delete-confirmation modal, reused by every resource table.
    // ---------------------------------------------------------------------
    window.showDeleteModal = function (url, entityLabel, onDeleted) {
        var existing = document.getElementById('delete-confirm-modal');
        if (existing) existing.remove();

        var modal = document.createElement('div');
        modal.id = 'delete-confirm-modal';
        modal.className = 'fixed inset-0 bg-gray-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4';
        modal.innerHTML =
            '<div class="bg-white rounded-xl shadow-xl max-w-md w-full p-6" role="alertdialog" aria-modal="true" aria-labelledby="delete-modal-title">' +
            '  <div class="flex items-center gap-3 mb-4">' +
            '    <div class="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">' +
            '      <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"></path>' +
            '      </svg>' +
            '    </div>' +
            '    <h3 id="delete-modal-title" class="text-lg font-semibold text-gray-900">Delete ' + escapeHtml(entityLabel) + '?</h3>' +
            '  </div>' +
            '  <p class="text-sm text-gray-500 mb-6">This action can\'t be undone.</p>' +
            '  <div class="flex justify-end gap-3">' +
            '    <button id="delete-cancel-btn" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">Cancel</button>' +
            '    <button id="delete-confirm-btn" class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 shadow-sm">Delete</button>' +
            '  </div>' +
            '</div>';

        document.body.appendChild(modal);
        document.getElementById('delete-confirm-btn').focus();

        function close() { modal.remove(); document.removeEventListener('keydown', onKey); }
        function onKey(e) { if (e.key === 'Escape') close(); }
        document.addEventListener('keydown', onKey);

        document.getElementById('delete-cancel-btn').addEventListener('click', close);
        modal.addEventListener('click', function (e) { if (e.target === modal) close(); });

        document.getElementById('delete-confirm-btn').addEventListener('click', function () {
            var btn = this;
            btn.disabled = true;
            btn.textContent = 'Deleting...';
            fetch(url, { method: 'DELETE' }).then(function (res) {
                close();
                if (res.ok) {
                    showToast(entityLabel + ' deleted');
                    if (typeof onDeleted === 'function') onDeleted();
                } else {
                    return res.json().catch(function () { return {}; }).then(function (data) {
                        showErrorToast(data.detail || data.error || 'Delete failed');
                    });
                }
            }).catch(function () {
                close();
                showErrorToast('Network error. The record was not deleted.');
            });
        });
    };

    // ---------------------------------------------------------------------
    // Dashboard summary counters
    // ---------------------------------------------------------------------
    function loadDashboardStats() {
        var endpoints = {
            'stat-users': '/api/user',
            'stat-orders': '/api/order',
            'stat-products': '/api/inventory',
            'stat-payments': '/api/payment',
        };

        Object.keys(endpoints).forEach(function (elementId) {
            var el = document.getElementById(elementId);
            if (!el) return;
            fetch(endpoints[elementId]).then(function (res) {
                if (res.ok) return res.json();
                throw new Error();
            }).then(function (data) {
                el.textContent = Array.isArray(data) ? data.length : '---';
            }).catch(function () {
                el.textContent = '---';
            });
        });
    }
})();
