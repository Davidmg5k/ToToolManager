// ToToolManager - Frontend JS

document.addEventListener('DOMContentLoaded', function() {
    loadDashboardStats();
    setupHTMXErrorHandling();
});

function setupHTMXErrorHandling() {
    document.body.addEventListener('htmx:responseError', function(e) {
        var xhr = e.detail.xhr;
        var message = 'An error occurred';
        try {
            var data = JSON.parse(xhr.responseText);
            message = data.error || message;
        } catch(ex) {}
        showErrorToast(message);
    });

    document.body.addEventListener('htmx:sendError', function() {
        showErrorToast('Network error. Please check your connection.');
    });
}

function showErrorToast(message) {
    var container = document.getElementById('error-toast-container');
    if (!container) return;

    var toast = document.createElement('div');
    toast.className = 'bg-red-500 text-white px-4 py-3 rounded-lg shadow-lg text-sm font-medium opacity-0 transition-opacity duration-300 flex items-center gap-2 max-w-sm';
    toast.innerHTML = '<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><span>' + message + '</span>';
    container.appendChild(toast);

    requestAnimationFrame(function() { toast.style.opacity = '1'; });

    setTimeout(function() {
        toast.style.opacity = '0';
        setTimeout(function() { toast.remove(); }, 300);
    }, 5000);
}

function loadDashboardStats() {
    var endpoints = {
        'stat-users': '/api/user',
        'stat-orders': '/api/order',
        'stat-products': '/api/inventory',
        'stat-payments': '/api/payment'
    };

    Object.keys(endpoints).forEach(function(elementId) {
        var el = document.getElementById(elementId);
        var url = endpoints[elementId];
        if (!el) return;
        fetch(url).then(function(res) {
            if (res.ok) return res.json();
            throw new Error();
        }).then(function(data) {
            el.textContent = Array.isArray(data) ? data.length : '\u2014';
        }).catch(function() {
            el.textContent = '\u2014';
        });
    });
}

function loadTable(tableId, url, rowMapper) {
    var tbody = document.getElementById(tableId);
    if (!tbody) return;
    fetch(url).then(function(res) {
        if (!res.ok) throw new Error('Failed to fetch');
        return res.json();
    }).then(function(data) {
        var items = Array.isArray(data) ? data : [];
        if (items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="99" class="px-6 py-8 text-center text-gray-500">No records found.</td></tr>';
            return;
        }
        tbody.innerHTML = items.map(rowMapper).join('');
    }).catch(function() {
        tbody.innerHTML = '<tr><td colspan="99" class="px-6 py-8 text-center text-red-500">Error loading data.</td></tr>';
    });
}

function showToast(message, type) {
    type = type || 'success';
    var container = document.getElementById('toast-container') || createToastContainer();
    var toast = document.createElement('div');
    var bgColor = type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-gray-500';
    toast.className = bgColor + ' text-white px-4 py-3 rounded-lg shadow-lg text-sm font-medium opacity-0 transition-opacity duration-300';
    toast.textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(function() { toast.style.opacity = '1'; });
    setTimeout(function() {
        toast.style.opacity = '0';
        setTimeout(function() { toast.remove(); }, 300);
    }, 3000);
}

function createToastContainer() {
    var container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'fixed bottom-4 right-4 z-50 space-y-2';
    document.body.appendChild(container);
    return container;
}

function confirmDelete(url, reloadFn) {
    if (!confirm('Are you sure you want to delete this record?')) return;
    fetch(url, { method: 'DELETE' }).then(function(res) {
        if (res.ok) {
            showToast('Deleted successfully');
            if (typeof reloadFn === 'function') reloadFn();
        } else {
            showToast('Delete failed', 'error');
        }
    }).catch(function() {
        showToast('Network error', 'error');
    });
}