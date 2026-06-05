// ============================================================
// Agent_CUG — ChatGPT 风格前端 JS
// ============================================================

(function () {
    'use strict';

    // ====== DOM 元素 ======
    const sidebar = document.getElementById('sidebar');
    const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
    const openSidebarBtn = document.getElementById('openSidebarBtn');
    const newChatBtn = document.getElementById('newChatBtn');
    const chatMessages = document.getElementById('chatMessages');
    const welcomeScreen = document.getElementById('welcomeScreen');
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const uploadBtn = document.getElementById('uploadBtn');
    const fileInput = document.getElementById('fileInput');
    const historyList = document.getElementById('historyList');
    const modelBadge = document.getElementById('modelBadge');

    // Panel 导航
    const navItems = document.querySelectorAll('.sidebar-nav-item');
    const chatPanel = document.getElementById('chatPanel');
    const ragPanel = document.getElementById('ragPanel');
    const settingsPanel = document.getElementById('settingsPanel');

    // RAG 元素
    const uploadDropzone = document.getElementById('uploadDropzone');
    const ragFileInput = document.getElementById('ragFileInput');
    const uploadStatus = document.getElementById('uploadStatus');
    const ragQueryInput = document.getElementById('ragQueryInput');
    const ragQueryBtn = document.getElementById('ragQueryBtn');
    const ragResults = document.getElementById('ragResults');
    const docCountEl = document.getElementById('docCount');

    // ====== 状态 ======
    let conversationId = null;
    let isStreaming = false;
    let messages = [];
    let conversations = [];

    // ====== 初始化 ======
    function init() {
        loadConfig();
        loadHistory();
        setupEventListeners();
        autoResizeInput();
    }

    async function loadConfig() {
        try {
            const resp = await fetch('/api/config');
            const config = await resp.json();
            if (modelBadge) modelBadge.textContent = config.llm_model || 'mimo-v2.5-pro';
            const ep = document.getElementById('settingProvider');
            const em = document.getElementById('settingModel');
            const ee = document.getElementById('settingEmbedding');
            const ed = document.getElementById('settingDocCount');
            if (ep) ep.textContent = config.model_provider || '-';
            if (em) em.textContent = config.llm_model || '-';
            if (ee) ee.textContent = config.embedding_model || '-';
            if (ed) ed.textContent = config.rag_document_count || '0';
            if (docCountEl) docCountEl.textContent = '文档: ' + (config.rag_document_count || 0);
        } catch (e) {
            console.warn('无法加载配置:', e);
        }
    }

    async function loadHistory() {
        try {
            const resp = await fetch('/api/history');
            const data = await resp.json();
            conversations = data.conversations || [];
            renderHistory();
        } catch (e) {
            console.warn('无法加载历史:', e);
        }
    }

    function renderHistory() {
        if (!historyList) return;

        if (conversations.length === 0) {
            historyList.innerHTML = '<div class="history-empty">暂无会话记录</div>';
            return;
        }

        historyList.innerHTML = conversations.map(conv => {
            const isActive = conv.id === conversationId;
            const time = formatTime(conv.created_at);
            return `
                <div class="history-item${isActive ? ' active' : ''}" data-id="${conv.id}" title="${escapeAttr(conv.title)}">
                    <span class="history-title">${escapeHtml(conv.title)}</span>
                    <span class="history-time">${time}</span>
                </div>
            `;
        }).join('');

        // 绑定点击事件
        historyList.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', () => {
                const id = item.dataset.id;
                // 简单实现：清空当前对话，设置 conversationId
                conversationId = id;
                renderHistory();
            });
        });
    }

    function formatTime(isoStr) {
        if (!isoStr) return '';
        try {
            const d = new Date(isoStr);
            const now = new Date();
            const diff = now - d;
            if (diff < 60000) return '刚刚';
            if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
            if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
            return d.toLocaleDateString('zh-CN');
        } catch (e) {
            return '';
        }
    }

    // ====== 事件监听 ======
    function setupEventListeners() {
        // 侧边栏
        toggleSidebarBtn.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            openSidebarBtn.style.display = sidebar.classList.contains('collapsed') ? 'flex' : 'none';
        });

        openSidebarBtn.addEventListener('click', () => {
            sidebar.classList.remove('collapsed');
            openSidebarBtn.style.display = 'none';
        });

        // 面板导航
        navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const panel = item.dataset.panel;
                switchPanel(panel);
                navItems.forEach(n => n.classList.remove('active'));
                item.classList.add('active');
            });
        });

        // 新对话
        newChatBtn.addEventListener('click', startNewChat);

        // 发送消息
        sendBtn.addEventListener('click', sendMessage);
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // 文件上传
        uploadBtn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', handleFileUpload);

        // 建议 chips
        document.querySelectorAll('.chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const prompt = chip.dataset.prompt;
                if (prompt) {
                    messageInput.value = prompt;
                    sendMessage();
                }
            });
        });

        // RAG 拖拽上传
        uploadDropzone.addEventListener('click', () => ragFileInput.click());
        uploadDropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadDropzone.classList.add('dragover');
        });
        uploadDropzone.addEventListener('dragleave', () => {
            uploadDropzone.classList.remove('dragover');
        });
        uploadDropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadDropzone.classList.remove('dragover');
            handleRagFiles(e.dataTransfer.files);
        });
        ragFileInput.addEventListener('change', (e) => {
            handleRagFiles(e.target.files);
        });

        // RAG 检索
        ragQueryBtn.addEventListener('click', doRagQuery);
        ragQueryInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') doRagQuery();
        });

        // 自动调整输入框高度
        messageInput.addEventListener('input', autoResizeInput);
    }

    function switchPanel(panel) {
        chatPanel.classList.remove('active');
        ragPanel.classList.remove('active');
        settingsPanel.classList.remove('active');

        if (panel === 'chat') chatPanel.classList.add('active');
        else if (panel === 'rag') { ragPanel.classList.add('active'); refreshDocCount(); }
        else if (panel === 'settings') { settingsPanel.classList.add('active'); loadConfig(); }
    }

    function autoResizeInput() {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
    }

    // ====== 聊天 ======
    function startNewChat() {
        conversationId = null;
        messages = [];
        // 只移除消息行，保留 welcomeScreen 在 DOM 中
        chatMessages.querySelectorAll('.message-row').forEach(function (el) { el.remove(); });
        if (welcomeScreen) {
            welcomeScreen.style.display = 'flex';
            if (!welcomeScreen.parentNode) {
                chatMessages.appendChild(welcomeScreen);
            }
        }
        messageInput.value = '';
        messageInput.focus();
        renderHistory();
    }

    async function sendMessage() {
        const text = messageInput.value.trim();
        if (!text || isStreaming) return;

        isStreaming = true;
        sendBtn.disabled = true;
        welcomeScreen.style.display = 'none';

        // 添加用户消息
        addMessage('user', text);
        messages.push({ role: 'user', content: text });
        messageInput.value = '';
        messageInput.style.height = 'auto';

        // 添加 AI 消息占位
        const assistantMsg = addMessage('assistant', '', true);
        const contentEl = assistantMsg.querySelector('.message-content');

        let fullText = '';

        try {
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    conversation_id: conversationId,
                }),
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || '请求失败: ' + response.status);
            }

            // SSE 标准解析
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // 按行解析 SSE 事件
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                let currentEvent = null;
                let currentData = '';

                for (const line of lines) {
                    if (line.startsWith('event: ')) {
                        currentEvent = line.slice(7).trim();
                    } else if (line.startsWith('data: ')) {
                        currentData = line.slice(6);
                    } else if (line === '') {
                        // 空行表示事件结束
                        if (currentEvent && currentData) {
                            handleSSEEvent(currentEvent, currentData);
                        }
                        currentEvent = null;
                        currentData = '';
                    }
                }

                // 处理最后一个未完成的事件
                if (currentEvent && currentData) {
                    handleSSEEvent(currentEvent, currentData);
                }
            }

            function handleSSEEvent(event, data) {
                if (event === 'token') {
                    fullText += data;
                    if (contentEl) {
                        contentEl.textContent = fullText;
                        contentEl.classList.add('streaming-cursor');
                    }
                    scrollToBottom();
                } else if (event === 'done') {
                    try {
                        const payload = JSON.parse(data);
                        conversationId = payload.conversation_id;
                        if (contentEl) {
                            contentEl.classList.remove('streaming-cursor');
                            contentEl.innerHTML = renderMarkdown(fullText);
                        }
                    } catch (e) {
                        if (contentEl) {
                            contentEl.classList.remove('streaming-cursor');
                        }
                    }
                } else if (event === 'error') {
                    if (contentEl) {
                        contentEl.textContent = '错误: ' + data;
                        contentEl.classList.remove('streaming-cursor');
                    }
                }
            }

            // 确保流式光标被移除
            if (contentEl && contentEl.classList.contains('streaming-cursor')) {
                contentEl.classList.remove('streaming-cursor');
                contentEl.innerHTML = renderMarkdown(fullText);
            }

            messages.push({ role: 'assistant', content: fullText });
            loadHistory(); // 刷新历史列表

        } catch (error) {
            if (contentEl) {
                contentEl.textContent = '网络错误: ' + error.message;
                contentEl.classList.remove('streaming-cursor');
            }
        }

        isStreaming = false;
        sendBtn.disabled = false;
        messageInput.focus();
        scrollToBottom();
    }

    function addMessage(role, content, streaming = false) {
        const row = document.createElement('div');
        row.className = 'message-row ' + role;

        const inner = document.createElement('div');
        inner.className = 'message-inner';

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = role === 'user' ? '👤' : '🤖';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        if (streaming) {
            contentDiv.classList.add('streaming-cursor');
        }
        contentDiv.textContent = content || '';

        inner.appendChild(avatar);
        inner.appendChild(contentDiv);
        row.appendChild(inner);
        chatMessages.appendChild(row);

        scrollToBottom();
        return row;
    }

    // 简单的 Markdown 渲染
    function renderMarkdown(text) {
        if (!text) return '';

        let html = escapeHtml(text);

        // 代码块 ```...```
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (match, lang, code) {
            const langLabel = lang ? ' <small>' + escapeHtml(lang) + '</small>' : '';
            return '<pre><code>' + langLabel + '\n' + escapeHtml(code) + '</code></pre>';
        });

        // 行内代码 `...`
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // 粗体 **...**
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // 斜体 *...*
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // 换行
        html = html.replace(/\n\n/g, '</p><p>');
        html = html.replace(/\n/g, '<br>');

        return '<p>' + html + '</p>';
    }

    function scrollToBottom() {
        requestAnimationFrame(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    // ====== 文件上传 ======
    async function handleFileUpload(e) {
        const files = e.target.files;
        if (!files.length) return;

        for (const file of files) {
            await uploadFile(file);
        }

        fileInput.value = '';
        refreshDocCount();
    }

    async function handleRagFiles(files) {
        if (!files.length) return;

        for (const file of files) {
            showUploadStatus('info', `⏳ 正在处理 ${file.name}...`);
            await uploadFile(file);
        }

        ragFileInput.value = '';
        refreshDocCount();
    }

    async function uploadFile(file) {
        try {
            const formData = new FormData();
            formData.append('file', file);

            const resp = await fetch('/api/rag/upload', {
                method: 'POST',
                body: formData,
            });

            const result = await resp.json();
            if (resp.ok) {
                showUploadStatus('success', `✅ ${file.name} — ${result.chunks} 个分块已导入`);
            } else {
                showUploadStatus('error', `❌ ${file.name} — ${result.detail || '上传失败'}`);
            }
        } catch (e) {
            showUploadStatus('error', `❌ ${file.name} — 网络错误`);
        }
    }

    function showUploadStatus(type, message) {
        if (!uploadStatus) return;
        const el = document.createElement('div');
        el.className = type;
        el.textContent = message;
        uploadStatus.appendChild(el);
        setTimeout(() => el.remove(), 5000);
    }

    async function refreshDocCount() {
        try {
            const resp = await fetch('/api/health');
            const data = await resp.json();
            if (docCountEl) docCountEl.textContent = '文档: ' + (data.document_count || 0);
            const settingDocCount = document.getElementById('settingDocCount');
            if (settingDocCount) settingDocCount.textContent = data.document_count || '0';
        } catch (e) {
            // ignore
        }
    }

    // ====== RAG 检索 ======
    async function doRagQuery() {
        const query = ragQueryInput.value.trim();
        if (!query) return;

        ragResults.innerHTML = '<p style="color: var(--text-tertiary)">检索中...</p>';

        try {
            const resp = await fetch('/api/rag/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, top_k: 5 }),
            });

            const data = await resp.json();

            if (!data.documents || data.documents.length === 0) {
                ragResults.innerHTML = '<p style="color: var(--text-tertiary)">未找到相关文档</p>';
                return;
            }

            ragResults.innerHTML = data.documents.map((doc, i) => `
                <div class="rag-result-item">
                    <div class="result-header">
                        <span>📄 ${escapeHtml(doc.source || '未知')}</span>
                        <span class="result-score">相似度: ${(doc.score * 100).toFixed(1)}%</span>
                    </div>
                    <div class="result-content">${escapeHtml(doc.content)}</div>
                </div>
            `).join('');

        } catch (e) {
            ragResults.innerHTML = '<p style="color: #ef4444">检索失败: ' + e.message + '</p>';
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function escapeAttr(text) {
        return text.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    // ====== 启动 ======
    init();
})();