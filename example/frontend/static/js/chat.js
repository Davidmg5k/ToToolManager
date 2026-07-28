// ToToolManager - AI Chat page
//
// Threading model
// ----------------
// The backend runs each sent message as a background task keyed by chat_id
// (see /api/chat/sessions/{id}/send -> task_id, /events, /status). That means
// more than one chat can genuinely be "running" at once, independent of
// which one is on screen. The frontend mirrors that: every chat with
// is_processing=true gets its own EventSource in `threads`, and switching
// the visible chat never tears another chat's connection down. Leaving the
// page and coming back (or a full reload) re-discovers running chats from
// the session list and reconnects automatically.
//
// URL routing
// -----------
// Selecting a chat pushes `/admin/chat/{chat_id}` via the History API, so
// the browser back/forward buttons and direct links work. For a hard
// refresh or a link to resolve server-side too, the backend route for
// /admin/chat/{chat_id} should render this same template — see CHANGES.md.

var threads = new Map(); // chat_id -> { eventSource, buffer, thinkingShown }
var nearBottom = true;

function chatApp() {
    return {
        currentChatId: null,
        currentTitle: '',
        messageCount: 0,
        chatSidebarOpen: window.innerWidth >= 768,
        streaming: false,
        showJumpToLatest: false,
        init() {
            window._chatApp = this;
            window._currentChatId = null;
            this._bootstrap();

            var mql = window.matchMedia('(min-width: 768px)');
            var self = this;
            mql.addEventListener('change', function (e) {
                if (!e.matches) self.chatSidebarOpen = false;
            });

            window.addEventListener('popstate', function () {
                var id = parseChatIdFromPath();
                if (id) selectChat(id, { pushUrl: false });
            });
        },
        onScroll() { onChatScroll(); },
        jumpToLatest() { scrollToBottom(true); this.showJumpToLatest = false; },
        async _bootstrap() {
            try {
                await loadSessions();
                const urlChatId = parseChatIdFromPath();
                const resp = await fetch('/api/chat/sessions');
                const sessions = await resp.json();

                if (urlChatId && sessions.some(function (s) { return s.chat_id === urlChatId; })) {
                    await selectChat(urlChatId, { pushUrl: false });
                    return;
                }
                if (sessions.length === 0) {
                    const f = new FormData();
                    f.append('title', 'New Chat');
                    await fetch('/api/chat/sessions', { method: 'POST', body: f });
                    await loadSessions();
                    const list = await (await fetch('/api/chat/sessions')).json();
                    if (list.length > 0) await selectChat(list[0].chat_id, { pushUrl: false });
                } else {
                    await selectChat(sessions[0].chat_id, { pushUrl: false });
                }
            } catch (e) {
                // ignore - sidebar will show its own error state
            }
        },
    };
}

function parseChatIdFromPath() {
    var match = window.location.pathname.match(/\/admin\/chat\/([^/?#]+)/);
    return match ? decodeURIComponent(match[1]) : null;
}

function formatTimestamp(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function relativeTime(iso) {
    if (!iso) return '';
    var diffMs = Date.now() - new Date(iso).getTime();
    var mins = Math.round(diffMs / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return mins + 'm ago';
    var hrs = Math.round(mins / 60);
    if (hrs < 24) return hrs + 'h ago';
    return Math.round(hrs / 24) + 'd ago';
}

// ---------------------------------------------------------------------
// Session list (left/right rail)
// ---------------------------------------------------------------------
function renderSessionItem(session) {
    var isProcessing = !!session.is_processing;
    var isActive = window._currentChatId === session.chat_id;

    const div = document.createElement('div');
    div.className = 'chat-session-item group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors ' +
        (isActive ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-gray-100') +
        (isProcessing ? ' chat-processing' : '');
    div.dataset.chatId = session.chat_id;
    div.dataset.processing = isProcessing ? '1' : '0';
    div.onclick = function () { selectChat(session.chat_id); };

    var icon = isProcessing
        ? '<svg class="w-3.5 h-3.5 text-indigo-500 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">' +
          '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>' +
          '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>'
        : '<svg class="w-3.5 h-3.5 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
          '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" ' +
          'd="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>';

    div.innerHTML =
        icon +
        '<div class="flex-1 min-w-0">' +
        '  <span class="chat-title block text-sm truncate">' + escapeHtml(session.title) + '</span>' +
        '  <span class="block text-[11px] ' + (isProcessing ? 'text-indigo-500 font-medium' : 'text-gray-400') + '">' +
        (isProcessing ? 'Responding…' : (session.updated_at ? relativeTime(session.updated_at) : (session.message_count + ' msgs'))) +
        '  </span>' +
        '</div>' +
        '<button type="button" onclick="event.stopPropagation(); startEditTitle(\'' + session.chat_id + '\', this)" ' +
        'class="hidden group-hover:inline-flex items-center p-1 rounded hover:bg-gray-200 shrink-0" title="Rename" aria-label="Rename chat">' +
        '<svg class="w-3 h-3 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" ' +
        'd="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>' +
        '</button>' +
        '<button type="button" onclick="event.stopPropagation(); deleteChat(\'' + session.chat_id + '\')" ' +
        'class="hidden group-hover:inline-flex items-center p-1 rounded hover:bg-red-100 shrink-0" title="Delete" aria-label="Delete chat">' +
        '<svg class="w-3 h-3 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" ' +
        'd="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>' +
        '</button>';
    return div;
}

async function loadSessions() {
    const list = document.getElementById('chat-sessions-list');
    if (!list) return;
    try {
        const resp = await fetch('/api/chat/sessions');
        const sessions = await resp.json();
        list.innerHTML = '';
        if (sessions.length === 0) {
            list.innerHTML = '<div class="text-xs text-gray-400 p-3 text-center">No chats yet — start one below.</div>';
            return;
        }
        sessions.forEach(function (s) {
            list.appendChild(renderSessionItem(s));
            // Rediscover and reconnect to anything still running, e.g. after a
            // full page reload or after leaving and coming back to /admin/chat.
            if (s.is_processing && !threads.has(s.chat_id)) {
                watchThread(s.chat_id);
            }
        });
    } catch (e) {
        list.innerHTML = '<div class="text-xs text-red-500 p-3 text-center">Couldn\'t load chats.</div>';
    }
}

window.addEventListener('chatSessionCreated', loadSessions);
window.addEventListener('chatSessionUpdated', loadSessions);
window.addEventListener('chatSessionDeleted', loadSessions);

// Light polling keeps sidebar state (message counts, is_processing) fresh
// even for chats nobody has an open connection to yet.
setInterval(loadSessions, 8000);

async function createNewChat() {
    const formData = new FormData();
    formData.append('title', 'New Chat');
    try {
        await fetch('/api/chat/sessions', { method: 'POST', body: formData });
        await loadSessions();
        const sessions = await (await fetch('/api/chat/sessions')).json();
        if (sessions.length > 0) await selectChat(sessions[0].chat_id);
    } catch (e) {
        showErrorToast('Could not start a new chat.');
    }
}

// ---------------------------------------------------------------------
// Message rendering
// ---------------------------------------------------------------------
function renderUserBubble(text, timestamp) {
    const div = document.createElement('div');
    div.className = 'flex justify-end gap-2.5';
    div.innerHTML =
        '<div class="flex flex-col items-end">' +
        '  <div class="bg-indigo-600 text-white rounded-2xl rounded-br-sm px-4 py-2 max-w-[85%] sm:max-w-lg shadow-sm"><p class="text-sm whitespace-pre-wrap break-words">' + escapeHtml(text) + '</p></div>' +
        (timestamp ? '  <span class="chat-timestamp">' + formatTimestamp(timestamp) + '</span>' : '') +
        '</div>' +
        '<div class="chat-avatar chat-avatar-user">You</div>';
    return div;
}

function renderAiBubble(text, timestamp) {
    const div = document.createElement('div');
    div.className = 'flex justify-start gap-2.5';
    div.innerHTML =
        '<div class="chat-avatar chat-avatar-ai">AI</div>' +
        '<div class="flex flex-col items-start min-w-0">' +
        '  <div class="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-2 max-w-[85%] sm:max-w-lg ai-bubble">' + marked.parse(text) + '</div>' +
        (timestamp ? '  <span class="chat-timestamp">' + formatTimestamp(timestamp) + '</span>' : '') +
        '</div>';
    return div;
}

function renderThinkingBubble() {
    const div = document.createElement('div');
    div.className = 'flex justify-start gap-2.5';
    div.id = 'thinking-bubble';
    div.innerHTML =
        '<div class="chat-avatar chat-avatar-ai">AI</div>' +
        '<div class="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-2 max-w-[85%] sm:max-w-lg ai-bubble">' +
        '<span class="inline-flex gap-1 items-center text-gray-400 text-sm">' +
        '<span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style="animation-delay:0ms"></span>' +
        '<span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style="animation-delay:150ms"></span>' +
        '<span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style="animation-delay:300ms"></span>' +
        '</span></div>';
    return div;
}

function renderMessages(messages) {
    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.innerHTML = '';
    messages.forEach(function (msg) {
        messagesDiv.appendChild(
            msg.role === 'user'
                ? renderUserBubble(msg.content, msg.created_at || msg.timestamp)
                : renderAiBubble(msg.content, msg.created_at || msg.timestamp)
        );
    });
    scrollToBottom(true);
}

// ---------------------------------------------------------------------
// Scroll behavior: never yank a user who scrolled up to read history;
// surface a "New messages" pill instead, like production chat UIs do.
// ---------------------------------------------------------------------
function scrollToBottom(force) {
    const el = document.getElementById('chat-messages');
    if (!el) return;
    if (force || nearBottom) {
        el.scrollTop = el.scrollHeight;
        nearBottom = true;
        window.dispatchEvent(new CustomEvent('chat-new-content', { detail: { hidden: false } }));
    }
}

function onChatScroll() {
    const el = document.getElementById('chat-messages');
    if (!el) return;
    nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (nearBottom) window.dispatchEvent(new CustomEvent('chat-new-content', { detail: { hidden: false } }));
}

function notifyNewContent() {
    if (!nearBottom) {
        window.dispatchEvent(new CustomEvent('chat-new-content', { detail: { hidden: true } }));
    } else {
        scrollToBottom(true);
    }
}

// ---------------------------------------------------------------------
// Selecting a chat: loads history, re-attaches to a running stream for
// THIS chat if one exists, and updates the URL without touching any
// other chat's connection.
// ---------------------------------------------------------------------
async function selectChat(chatId, opts) {
    opts = opts || {};
    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.innerHTML = '<div class="flex justify-center pt-8"><div class="animate-pulse text-gray-400 text-sm">Loading messages…</div></div>';

    try {
        const resp = await fetch('/api/chat/sessions/' + chatId + '/messages');
        const messages = await resp.json();

        window._currentChatId = chatId;
        renderMessages(messages);

        const sessionItem = document.querySelector('[data-chat-id="' + chatId + '"]');
        const title = sessionItem ? (sessionItem.querySelector('.chat-title')?.textContent || 'Chat') : 'Chat';

        document.querySelectorAll('.chat-session-item').forEach(function (el) {
            el.classList.toggle('bg-indigo-50', el.dataset.chatId === chatId);
            el.classList.toggle('text-indigo-700', el.dataset.chatId === chatId);
        });

        if (opts.pushUrl !== false) {
            const path = '/admin/chat/' + chatId;
            if (window.location.pathname !== path) window.history.pushState({ chatId: chatId }, '', path);
        }

        const thread = threads.get(chatId);
        const isStreaming = !!thread;
        window.dispatchEvent(new CustomEvent('chat-select', {
            detail: { chat_id: chatId, title: title, count: messages.length },
        }));
        window.dispatchEvent(new CustomEvent('chat-streaming', { detail: { active: isStreaming } }));

        if (thread) {
            // Re-attach: show whatever has streamed in so far for this chat.
            const bubble = renderThinkingBubble();
            messagesDiv.appendChild(bubble);
            if (thread.buffer) {
                bubble.remove();
                const liveBubble = renderAiBubble(thread.buffer);
                liveBubble.id = 'live-ai-bubble';
                messagesDiv.appendChild(liveBubble);
            }
            scrollToBottom(true);
        } else {
            watchThread(chatId); // no-op if it isn't actually running server-side
        }
    } catch (e) {
        showErrorToast('Could not load that conversation.');
    }
}

// ---------------------------------------------------------------------
// Per-chat streaming connection. Multiple of these can be open at once —
// nothing here closes a connection that belongs to a different chat_id.
// ---------------------------------------------------------------------
function watchThread(chatId) {
    if (threads.has(chatId)) return;

    fetch('/api/chat/sessions/' + chatId + '/status')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.status === 'running' || data.status === 'pending') {
                connectThread(chatId);
            }
        })
        .catch(function () { /* ignore - will retry on next poll */ });
}

function connectThread(chatId) {
    if (threads.has(chatId)) return;

    const thread = { eventSource: null, buffer: '' };
    threads.set(chatId, thread);

    if (window._currentChatId === chatId) {
        window.dispatchEvent(new CustomEvent('chat-streaming', { detail: { active: true } }));
        if (!document.getElementById('thinking-bubble')) {
            const messagesDiv = document.getElementById('chat-messages');
            messagesDiv.appendChild(renderThinkingBubble());
            scrollToBottom(true);
        }
    }

    const es = new EventSource('/api/chat/sessions/' + chatId + '/events');
    thread.eventSource = es;

    es.onmessage = function (event) {
        if (event.data === '[DONE]') {
            finishThread(chatId);
            return;
        }
        try {
            const parsed = JSON.parse(event.data);

            if (parsed.type === 'token' && parsed.text) {
                thread.buffer += parsed.text;
                updateLiveBubbleIfActive(chatId, thread.buffer);
            }

            if (parsed.type === 'status' && parsed.status) {
                const item = document.querySelector('.chat-session-item[data-chat-id="' + chatId + '"]');
                if (item) item.dataset.processing = (parsed.status === 'running' || parsed.status === 'pending') ? '1' : '0';
            }
        } catch (e) { /* ignore malformed SSE chunk */ }
    };

    es.onerror = function () {
        es.close();
        var stillTracked = threads.has(chatId);
        threads.delete(chatId);
        if (!stillTracked) return; // already wrapped up cleanly via [DONE]

        if (window._currentChatId === chatId && !thread.buffer) {
            const el = document.getElementById('thinking-bubble');
            if (el) el.remove();
        }
        // Fall back to polling so a dropped connection doesn't strand the UI.
        pollUntilDone(chatId);
    };
}

function updateLiveBubbleIfActive(chatId, text) {
    if (window._currentChatId !== chatId) return;
    const messagesDiv = document.getElementById('chat-messages');
    const thinkingEl = document.getElementById('thinking-bubble');
    if (thinkingEl) thinkingEl.remove();

    let liveBubble = document.getElementById('live-ai-bubble');
    if (!liveBubble) {
        liveBubble = renderAiBubble('');
        liveBubble.id = 'live-ai-bubble';
        messagesDiv.appendChild(liveBubble);
    }
    liveBubble.querySelector('.ai-bubble').innerHTML = marked.parse(text);
    notifyNewContent();
}

function finishThread(chatId) {
    const thread = threads.get(chatId);
    if (thread && thread.eventSource) thread.eventSource.close();
    threads.delete(chatId);

    loadSessions();

    if (window._currentChatId === chatId) {
        window.dispatchEvent(new CustomEvent('chat-streaming', { detail: { active: false } }));
        window.dispatchEvent(new CustomEvent('chat-stream-done'));
        const liveBubble = document.getElementById('live-ai-bubble');
        if (liveBubble) liveBubble.removeAttribute('id');
        // Re-fetch so the final, canonical message (with its real timestamp
        // and id) replaces the locally-streamed approximation.
        fetch('/api/chat/sessions/' + chatId + '/messages')
            .then(function (r) { return r.json(); })
            .then(function (messages) { if (window._currentChatId === chatId) renderMessages(messages); })
            .catch(function () { /* keep what's on screen */ });
    } else {
        showToast('A chat finished responding.');
    }
}

function pollUntilDone(chatId, attempt) {
    attempt = attempt || 0;
    if (attempt > 120) return; // ~6 minutes at 3s intervals, then give up quietly

    fetch('/api/chat/sessions/' + chatId + '/status')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.status === 'completed' || data.status === 'failed' || data.status === 'idle') {
                finishThread(chatId);
            } else {
                setTimeout(function () { pollUntilDone(chatId, attempt + 1); }, 3000);
            }
        })
        .catch(function () {
            setTimeout(function () { pollUntilDone(chatId, attempt + 1); }, 4000);
        });
}

// ---------------------------------------------------------------------
// Sending a message
// ---------------------------------------------------------------------
async function sendMessage(e) {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    const chatId = window._currentChatId;
    if (!chatId) {
        showErrorToast('Start or select a chat first.');
        return;
    }
    if (threads.has(chatId)) {
        showErrorToast('This chat is still responding — wait a moment before sending another message.');
        return;
    }

    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.appendChild(renderUserBubble(text, new Date().toISOString()));
    messagesDiv.appendChild(renderThinkingBubble());
    scrollToBottom(true);

    input.value = '';
    input.focus();

    try {
        const formData = new FormData();
        formData.append('message', text);
        const resp = await fetch('/api/chat/sessions/' + chatId + '/send', { method: 'POST', body: formData });

        if (!resp.ok) {
            const errData = await resp.json().catch(function () { return {}; });
            throw new Error(errData.detail || 'Failed to start the response');
        }

        const data = await resp.json();
        if (data.task_id) connectThread(chatId);
    } catch (err) {
        const thinkingEl = document.getElementById('thinking-bubble');
        if (thinkingEl) thinkingEl.remove();
        showErrorToast('Could not send that message: ' + err.message);
    }
}

// ---------------------------------------------------------------------
// Rename / delete
// ---------------------------------------------------------------------
function deleteChat(chatId) {
    showDeleteModal('/api/chat/sessions/' + chatId, 'this chat', async function () {
        const thread = threads.get(chatId);
        if (thread && thread.eventSource) thread.eventSource.close();
        threads.delete(chatId);

        const wasCurrent = window._currentChatId === chatId;
        window.dispatchEvent(new CustomEvent('chatSessionDeleted'));
        await loadSessions();

        if (wasCurrent) {
            window._currentChatId = null;
            renderMessages([]);
            const sessions = await (await fetch('/api/chat/sessions')).json();
            if (sessions.length > 0) {
                await selectChat(sessions[0].chat_id);
            } else {
                window.history.pushState({}, '', '/admin/chat');
            }
        }
    });
}

function startEditTitle(chatId, btn) {
    const item = btn.closest('.chat-session-item');
    const span = item.querySelector('.chat-title');
    const currentTitle = span.textContent;
    const escapedVal = currentTitle.replace(/"/g, '&quot;');
    span.outerHTML = '<input type="text" value="' + escapedVal + '" class="chat-title w-full text-sm px-1 py-0.5 border border-indigo-300 rounded focus:ring-1 focus:ring-indigo-500" ' +
        'onblur="saveTitle(\'' + chatId + '\', this.value)" ' +
        'onkeydown="if(event.key===\'Enter\') this.blur(); if(event.key===\'Escape\') this.blur();" />';
    const inputEl = item.querySelector('input.chat-title');
    inputEl.focus();
    inputEl.select();
}

async function saveTitle(chatId, newTitle) {
    if (!newTitle.trim()) {
        loadSessions();
        return;
    }
    const formData = new FormData();
    formData.append('title', newTitle.trim());
    try {
        await fetch('/api/chat/sessions/' + chatId, { method: 'PATCH', body: formData });
        await loadSessions();
        if (window._currentChatId === chatId) {
            window.dispatchEvent(new CustomEvent('chat-select', { detail: { chat_id: chatId, title: newTitle.trim() } }));
        }
    } catch (e) {
        showErrorToast('Could not rename the chat.');
        loadSessions();
    }
}
