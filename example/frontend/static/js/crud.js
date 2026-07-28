// ToToolManager - Generic CRUD resource controller
//
// Every admin list page (Users, Orders, Inventory, Payments, Notifications)
// shares the exact same shape: a searchable/sortable table, a create form,
// an edit form and a delete confirmation. Instead of re-implementing that
// per page, each page registers a small config object describing *what*
// is different (endpoint, id field, columns, form fields) and includes
// component/crud-page.html, which binds to this single Alpine component.
//
// Usage in a page template:
//   <script>
//     window.CRUD_CONFIGS = window.CRUD_CONFIGS || {};
//     window.CRUD_CONFIGS['users'] = { ...config... };
//   </script>
//   {% include 'component/crud-page.html' %}   (with resource_id='users')

window.CRUD_CONFIGS = window.CRUD_CONFIGS || {};

document.addEventListener('alpine:init', function () {
    Alpine.data('crudResource', function (resourceId) {
        var config = window.CRUD_CONFIGS[resourceId];
        if (!config) {
            console.error('No CRUD config registered for "' + resourceId + '"');
            config = { label: 'Item', endpoint: '#', idField: 'id', columns: [], createFields: [], editFields: [] };
        }

        return {
            // -- static config, exposed for the template ---------------------
            config: config,
            columns: config.columns,

            // -- state ---------------------------------------------------------
            items: [],
            loading: true,
            loadError: false,
            query: '',
            sortKey: null,
            sortDir: 1,

            modalOpen: false,
            modalMode: 'create', // 'create' | 'edit'
            form: {},
            editingId: null,
            submitting: false,

            // -- lifecycle -------------------------------------------------------
            init() {
                this.load();
            },

            async load() {
                this.loading = true;
                this.loadError = false;
                try {
                    const res = await fetch(this.config.endpoint);
                    if (!res.ok) throw new Error('bad status');
                    const data = await res.json();
                    this.items = Array.isArray(data) ? data : [];
                } catch (e) {
                    this.loadError = true;
                    this.items = [];
                } finally {
                    this.loading = false;
                }
            },

            // -- derived state -----------------------------------------------
            get filteredItems() {
                let rows = this.items;
                const q = this.query.trim().toLowerCase();
                if (q) {
                    rows = rows.filter((item) =>
                        this.columns.some((col) => String(this.rawValue(col, item) ?? '').toLowerCase().includes(q))
                    );
                }
                if (this.sortKey) {
                    const key = this.sortKey;
                    const dir = this.sortDir;
                    rows = [...rows].sort((a, b) => {
                        const av = this.rawValue({ key }, a);
                        const bv = this.rawValue({ key }, b);
                        if (av == null) return 1;
                        if (bv == null) return -1;
                        if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir;
                        return String(av).localeCompare(String(bv)) * dir;
                    });
                }
                return rows;
            },

            sortBy(col) {
                if (!col.sortable) return;
                if (this.sortKey === col.key) {
                    this.sortDir = -this.sortDir;
                } else {
                    this.sortKey = col.key;
                    this.sortDir = 1;
                }
            },

            // -- cell formatting -----------------------------------------------
            rawValue(col, item) {
                return typeof col.value === 'function' ? col.value(item) : item[col.key];
            },

            formatCell(col, item) {
                const raw = this.rawValue(col, item);
                if (col.type === 'currency') {
                    const n = Number(raw);
                    return '$' + (isNaN(n) ? '0.00' : n.toFixed(2));
                }
                if (col.type === 'badge') {
                    const cls = (col.badgeMap && col.badgeMap[raw]) || 'bg-gray-100 text-gray-700';
                    return '<span class="inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ' + cls + '">' + escapeHtml(raw ?? '—') + '</span>';
                }
                return escapeHtml(raw == null || raw === '' ? '—' : raw);
            },

            // -- modal: create / edit -------------------------------------------
            get activeFields() {
                return this.modalMode === 'create' ? this.config.createFields : this.config.editFields;
            },

            openCreate() {
                this.modalMode = 'create';
                this.editingId = null;
                const form = {};
                this.config.createFields.forEach((f) => { form[f.name] = f.default ?? ''; });
                this.form = form;
                this.modalOpen = true;
                this.$nextTick(() => this.focusFirstField());
            },

            openEdit(item) {
                this.modalMode = 'edit';
                this.editingId = item[this.config.idField];
                const form = {};
                this.config.editFields.forEach((f) => { form[f.name] = f.fromItem ? f.fromItem(item) : (item[f.name] ?? ''); });
                this.form = form;
                this.modalOpen = true;
                this.$nextTick(() => this.focusFirstField());
            },

            focusFirstField() {
                const el = this.$refs.modal && this.$refs.modal.querySelector('input, select, textarea');
                if (el) el.focus();
            },

            closeModal() {
                this.modalOpen = false;
                this.submitting = false;
            },

            async submit() {
                this.submitting = true;
                const fields = this.activeFields;
                const payload = {};
                fields.forEach((f) => {
                    let v = this.form[f.name];
                    if (f.type === 'number' && v !== '') v = parseFloat(v);
                    // On edit, an untouched optional field (e.g. password) is omitted
                    // so the backend keeps the existing value.
                    if (this.modalMode === 'edit' && f.optionalOnEdit && (v === '' || v == null)) return;
                    payload[f.name] = v;
                });

                try {
                    let res;
                    if (this.modalMode === 'create') {
                        const body = new URLSearchParams();
                        Object.entries(payload).forEach(([k, v]) => body.append(k, v ?? ''));
                        res = await fetch(this.config.endpoint, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                            body,
                        });
                    } else {
                        res = await fetch(this.config.endpoint + '/' + this.editingId, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload),
                        });
                    }

                    if (res.ok) {
                        showToast(this.config.label + (this.modalMode === 'create' ? ' created' : ' updated'));
                        this.closeModal();
                        await this.load();
                    } else {
                        const err = await res.json().catch(() => ({}));
                        showErrorToast(err.detail || err.error || 'Could not save ' + this.config.label.toLowerCase() + '.');
                    }
                } catch (e) {
                    showErrorToast('Network error. Nothing was saved.');
                } finally {
                    this.submitting = false;
                }
            },

            remove(item) {
                const label = this.config.label + (config.itemLabel ? ' “' + config.itemLabel(item) + '”' : '');
                showDeleteModal(this.config.endpoint + '/' + item[this.config.idField], label, () => this.load());
            },
        };
    });
});
