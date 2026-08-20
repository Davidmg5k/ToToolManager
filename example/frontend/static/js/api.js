// ToToolManager - Centralized API Client
//
// All frontend HTTP calls go through this module. It provides:
// - Consistent response envelope handling ({ success, data, error })
// - Automatic error toast on failure
// - HTMX header support (HX-Request) when needed
// - Form-data and JSON body helpers
//
// Usage:
//   const users = await API.get('/api/user');
//   const user  = await API.post('/api/user', { user_name: '...', email: '...', password: '...' });
//   const updated = await API.patch('/api/user/' + id, { user_name: 'New Name' });
//   await API.del('/api/user/' + id);

window.API = (function () {
    'use strict';

    var BASE = '';

    // -----------------------------------------------------------------
    // Core request method
    // -----------------------------------------------------------------
    async function request(method, path, body, opts) {
        opts = opts || {};
        var url = path.indexOf('http') === 0 ? path : BASE + path;

        var headers = opts.headers || {};
        var fetchOpts = { method: method, headers: headers };

        if (body !== undefined && body !== null) {
            if (body instanceof FormData || body instanceof URLSearchParams) {
                fetchOpts.body = body;
                // Let browser set Content-Type (boundary for FormData, urlencoded for URLSearchParams)
            } else if (typeof body === 'object') {
                headers['Content-Type'] = 'application/json';
                fetchOpts.body = JSON.stringify(body);
            } else {
                fetchOpts.body = body;
            }
        }

        if (opts.htmx) {
            headers['HX-Request'] = 'true';
        }

        var res = await fetch(url, fetchOpts);

        // Handle no-content responses (204, or empty 200)
        if (res.status === 204) {
            return { success: true, data: null };
        }

        var text = await res.text();
        var data;
        try {
            data = JSON.parse(text);
        } catch (e) {
            data = { success: res.ok, data: null, error: text || 'Unexpected response' };
        }

        // Handle HTMX redirect header
        var hxRedirect = res.headers.get('HX-Redirect');
        if (hxRedirect) {
            window.location.href = hxRedirect;
            return data;
        }

        // Auto-show error toast on failure
        if (!data.success && !opts.silent) {
            var msg = data.error || 'Something went wrong';
            if (typeof showErrorToast === 'function') {
                showErrorToast(msg);
            }
        }

        return data;
    }

    // -----------------------------------------------------------------
    // Convenience methods
    // -----------------------------------------------------------------
    return {
        request: request,

        get: function (path, opts) {
            return request('GET', path, null, opts);
        },

        post: function (path, body, opts) {
            return request('POST', path, body, opts);
        },

        patch: function (path, body, opts) {
            return request('PATCH', path, body, opts);
        },

        del: function (path, opts) {
            return request('DELETE', path, null, opts);
        },

        // Post with FormData (for HTMX form submissions)
        postForm: function (path, formData, opts) {
            return request('POST', path, formData, opts);
        },

        patchForm: function (path, formData, opts) {
            return request('PATCH', path, formData, opts);
        },
    };
})();
