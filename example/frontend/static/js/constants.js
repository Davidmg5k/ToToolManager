// ToToolManager - Shared Constants & CRUD Configs
//
// Centralizes API endpoints, enum values, and CRUD page configurations
// so they are defined once and reused across all admin pages.

window.APP_CONSTANTS = {
    // -----------------------------------------------------------------
    // API Endpoints
    // -----------------------------------------------------------------
    endpoints: {
        user: '/api/user',
        order: '/api/order',
        inventory: '/api/inventory',
        payment: '/api/payment',
        notification: '/api/notification',
        chat: '/api/chat',
        dashboard: '/api/dashboard',
    },

    // -----------------------------------------------------------------
    // Enum values (mirrors backend Python enums)
    // -----------------------------------------------------------------
    enums: {
        orderStatus: ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled'],
        paymentMethod: ['credit_card', 'debit_card', 'bank_transfer', 'cash'],
        paymentStatus: ['pending', 'completed', 'failed', 'refunded'],
        notificationChannel: ['email', 'sms', 'push'],
        notificationStatus: ['pending', 'sent', 'delivered', 'failed'],
    },

    // -----------------------------------------------------------------
    // Badge color maps (status -> Tailwind classes)
    // -----------------------------------------------------------------
    badges: {
        orderStatus: {
            pending: 'bg-yellow-100 text-yellow-800',
            confirmed: 'bg-blue-100 text-blue-800',
            shipped: 'bg-purple-100 text-purple-800',
            delivered: 'bg-green-100 text-green-800',
            cancelled: 'bg-red-100 text-red-800',
        },
        paymentStatus: {
            completed: 'bg-success-50 text-success-700 border border-success-200',
            pending: 'bg-brand-50 text-brand-700 border border-brand-200',
            refunded: 'bg-paper-200 text-ink-700 border border-paper-400',
            failed: 'bg-danger-50 text-danger-700 border border-danger-200',
        },
        notificationStatus: {
            sent: 'bg-success-50 text-success-700 border border-success-200',
            delivered: 'bg-accent-50 text-accent-700 border border-accent-200',
            pending: 'bg-brand-50 text-brand-700 border border-brand-200',
            failed: 'bg-danger-50 text-danger-700 border border-danger-200',
        },
    },
};

// -----------------------------------------------------------------
// CRUD Configs (single source of truth for all admin pages)
// -----------------------------------------------------------------
window.CRUD_CONFIGS = {
    users: {
        label: 'User',
        endpoint: window.APP_CONSTANTS.endpoints.user,
        idField: 'user_id',
        itemLabel: function (item) { return item.user_name; },
        columns: [
            { key: 'user_name', label: 'Name', sortable: true },
            { key: 'email', label: 'Email', sortable: true },
        ],
        createFields: [
            { name: 'user_name', label: 'Full name', type: 'text', required: true, placeholder: 'Jane Cooper' },
            { name: 'email', label: 'Email', type: 'email', required: true, placeholder: 'jane@example.com' },
            { name: 'password', label: 'Password', type: 'password', required: true, placeholder: 'At least 8 characters' },
        ],
        editFields: [
            { name: 'user_name', label: 'Full name', type: 'text', required: true },
            { name: 'email', label: 'Email', type: 'email', required: true },
            { name: 'password', label: 'Password', type: 'password', optionalOnEdit: true, editPlaceholder: 'Leave empty to keep current' },
        ],
    },

    orders: {
        label: 'Order',
        endpoint: window.APP_CONSTANTS.endpoints.order,
        idField: 'order_id',
        itemLabel: function (item) { return item.product_name; },
        columns: [
            { key: 'product_name', label: 'Product', sortable: true },
            { key: 'quantity', label: 'Qty', sortable: true },
            { key: 'total', label: 'Total', type: 'currency', sortable: true, value: function (item) { return item.total ?? (item.quantity * item.unit_price); } },
            {
                key: 'status', label: 'Status', type: 'badge', sortable: true,
                badgeMap: window.APP_CONSTANTS.badges.orderStatus,
            },
        ],
        createFields: [
            { name: 'user_id', label: 'User ID', type: 'text', required: true, placeholder: 'Paste the customer\'s user ID' },
            { name: 'product_name', label: 'Product name', type: 'text', required: true },
            { name: 'quantity', label: 'Quantity', type: 'number', required: true, min: 1, default: 1 },
            { name: 'unit_price', label: 'Unit price', type: 'number', required: true, step: '0.01', min: 0 },
        ],
        editFields: [
            { name: 'product_name', label: 'Product name', type: 'text', required: true },
            { name: 'quantity', label: 'Quantity', type: 'number', required: true, min: 1 },
            { name: 'unit_price', label: 'Unit price', type: 'number', required: true, step: '0.01', min: 0 },
            {
                name: 'status', label: 'Status', type: 'select', required: true,
                options: [
                    { value: 'pending', label: 'Pending' },
                    { value: 'confirmed', label: 'Confirmed' },
                    { value: 'shipped', label: 'Shipped' },
                    { value: 'delivered', label: 'Delivered' },
                    { value: 'cancelled', label: 'Cancelled' },
                ],
            },
        ],
    },

    inventory: {
        label: 'Product',
        endpoint: window.APP_CONSTANTS.endpoints.inventory,
        idField: 'product_id',
        itemLabel: function (item) { return item.name; },
        columns: [
            { key: 'name', label: 'Name', sortable: true },
            { key: 'sku', label: 'SKU', sortable: true },
            { key: 'price', label: 'Price', type: 'currency', sortable: true },
            { key: 'stock', label: 'Stock', sortable: true },
        ],
        createFields: [
            { name: 'name', label: 'Product name', type: 'text', required: true },
            { name: 'sku', label: 'SKU', type: 'text', required: true },
            { name: 'price', label: 'Price', type: 'number', required: true, step: '0.01', min: 0 },
            { name: 'stock', label: 'Initial stock', type: 'number', required: true, min: 0, default: 0 },
            { name: 'description', label: 'Description', type: 'textarea', placeholder: 'Optional' },
        ],
        editFields: [
            { name: 'name', label: 'Product name', type: 'text', required: true },
            { name: 'sku', label: 'SKU', type: 'text', required: true },
            { name: 'price', label: 'Price', type: 'number', required: true, step: '0.01', min: 0 },
            { name: 'stock', label: 'Stock', type: 'number', required: true, min: 0 },
            { name: 'description', label: 'Description', type: 'textarea', placeholder: 'Optional' },
        ],
    },

    payments: {
        label: 'Payment',
        endpoint: window.APP_CONSTANTS.endpoints.payment,
        idField: 'payment_id',
        itemLabel: function (item) { return item.order_id; },
        columns: [
            { key: 'order_id', label: 'Order', sortable: true },
            { key: 'amount', label: 'Amount', type: 'currency', sortable: true },
            { key: 'method', label: 'Method', sortable: true },
            {
                key: 'status', label: 'Status', type: 'badge', sortable: true,
                badgeMap: window.APP_CONSTANTS.badges.paymentStatus,
            },
        ],
        createFields: [
            { name: 'order_id', label: 'Order ID', type: 'text', required: true },
            { name: 'amount', label: 'Amount', type: 'number', required: true, step: '0.01', min: 0.01 },
            {
                name: 'method', label: 'Method', type: 'select', required: true,
                options: [
                    { value: 'credit_card', label: 'Credit Card' },
                    { value: 'debit_card', label: 'Debit Card' },
                    { value: 'bank_transfer', label: 'Bank Transfer' },
                    { value: 'cash', label: 'Cash' },
                ],
            },
        ],
        editFields: [
            { name: 'amount', label: 'Amount', type: 'number', required: true, step: '0.01', min: 0.01 },
            {
                name: 'status', label: 'Status', type: 'select', required: true,
                options: [
                    { value: 'pending', label: 'Pending' },
                    { value: 'completed', label: 'Completed' },
                    { value: 'failed', label: 'Failed' },
                    { value: 'refunded', label: 'Refunded' },
                ],
            },
        ],
    },

    notifications: {
        label: 'Notification',
        endpoint: window.APP_CONSTANTS.endpoints.notification,
        idField: 'notification_id',
        itemLabel: function (item) { return item.subject; },
        submitLabel: 'Send',
        columns: [
            { key: 'channel', label: 'Channel', sortable: true },
            { key: 'recipient', label: 'Recipient', sortable: true },
            { key: 'subject', label: 'Subject', sortable: true },
            {
                key: 'status', label: 'Status', type: 'badge', sortable: true,
                badgeMap: window.APP_CONSTANTS.badges.notificationStatus,
            },
        ],
        createFields: [
            { name: 'user_id', label: 'User ID', type: 'text', required: true },
            {
                name: 'channel', label: 'Channel', type: 'select', required: true,
                options: [
                    { value: 'email', label: 'Email' },
                    { value: 'sms', label: 'SMS' },
                    { value: 'push', label: 'Push' },
                ],
            },
            { name: 'recipient', label: 'Recipient', type: 'text', required: true, placeholder: 'Email or phone number' },
            { name: 'subject', label: 'Subject', type: 'text', required: true },
            { name: 'body', label: 'Message', type: 'textarea', required: true },
        ],
        editFields: [
            { name: 'subject', label: 'Subject', type: 'text', required: true },
            { name: 'body', label: 'Message', type: 'textarea', required: true },
            {
                name: 'status', label: 'Status', type: 'select', required: true,
                options: [
                    { value: 'pending', label: 'Pending' },
                    { value: 'sent', label: 'Sent' },
                    { value: 'delivered', label: 'Delivered' },
                    { value: 'failed', label: 'Failed' },
                ],
            },
        ],
    },
};
