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

    // ====== 初始化 ======
    function init() {
        loadConfig();
        setupEventListeners();
        autoResizeInput();
    }

    async function loadConfig() {
        try {
            const resp = await fetch('/api/config');
            const config = await resp.json();
            if (modelBadge) modelBadge.textContent = config.llm_model || 'mimo-v2.5-pro';
            document.getElementById('settingProvider').textContent = config.model_provider || '-';
            document.getElementById('settingModel').textContent = config.llm_model || '-';
            document.getElementById('settingEmbedding').textContent = config.embedding_model || '-';
            document.getElementById('settingDocCount').textContent = config.rag_document_count || '0';
            if (docCountEl) docCountEl.textContent = '文档: ' + (config.rag_document_count || 0);
        } catch (e) {
            console.warn('无法加载配置:', e);
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
        chatMessages.innerHTML = '';
        welcomeScreen.style.display = 'flex';
        messageInput.value = '';
        messageInput.focus();
    }

    async function sendMessage() {
        const text = messageInput.value.trim();
        if (!text || isStreaming) return;

        isStreaming = true;
        sendBtn.disabled = true;
        welcomeScreen.style.display = 'none';

        // 添加用户消息
        addMessage('user', text);
        messageInput.value = '';
        messageInput.style.height = 'auto';

        // 添加 AI 消息占位
        const assistantMsg = addMessage('assistant', '', true);

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
                throw new Error('请求失败: ' + response.status);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let fullText = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data === '[DONE]') continue;

                        try {
                            const parsed = JSON.parse(data);
                            if (parsed.event === 'token') {
                                fullText += parsed.data;
                                updateMessageContent(assistantMsg, fullText, true);
                            } else if (parsed.event === 'done') {
                                const payload = JSON.parse(parsed.data);
                                conversationId = payload.conversation_id;
                                updateMessageContent(assistantMsg, fullText, false);
                            } else if (parsed.event === 'error') {
                                updateMessageContent(assistantMsg, '错误: ' + parsed.data, false);
                            }
                        } catch (e) {
                            // 纯文本 token
                            if (data && data.length > 0 && data !== '[DONE]') {
                                fullText += data;
                                updateMessageContent(assistantMsg, fullText, true);
                            }
                        }
                    }
                }
            }

            updateMessageContent(assistantMsg, fullText, false);
            messages.push({ role: 'user', content: text });
            messages.push({ role: 'assistant', content: fullText });

        } catch (error) {
            updateMessageContent(assistantMsg, '网络错误: ' + error.message, false);
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
        return contentDiv;
    }

    function updateMessageContent(el, text, streaming) {
        el.textContent = text;
        if (streaming) {
            el.classList.add('streaming-cursor');
        } else {
            el.classList.remove('streaming-cursor');
        }
        scrollToBottom();
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
            try {
                const formData = new FormData();
                formData.append('file', file);

                const resp = await fetch('/api/rag/upload', {
                    method: 'POST',
                    body: formData,
                });

                const result = await resp.json();
                if (resp.ok) {
                    showUploadStatus('success', ✅  —  个分块已导入);
                } else {
                    showUploadStatus('error', ❌  — );
                }
            } catch (e) {
                showUploadStatus('error', ❌  — 网络错误);
            }
        }

        fileInput.value = '';
        refreshDocCount();
    }

    async function handleRagFiles(files) {
        if (!files.length) return;

        for (const file of files) {
            try {
                showUploadStatus('info', ⏳ 正在处理 ...);

                const formData = new FormData();
                formData.append('file', file);

                const resp = await fetch('/api/rag/upload', {
                    method: 'POST',
                    body: formData,
                });

                const result = await resp.json();
                if (resp.ok) {
                    showUploadStatus('success', ✅  —  个分块已导入);
                } else {
                    showUploadStatus('error', ❌  — );
                }
            } catch (e) {
                showUploadStatus('error', ❌  — 网络错误);
            }
        }

        ragFileInput.value = '';
        refreshDocCount();
    }

    function showUploadStatus(type, message) {
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
        } catch (e) {}
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

            ragResults.innerHTML = data.documents.map((doc, i) => 
                <div class="rag-result-item">
                    <div class="result-header">
                        <span>📄 </span>
                        <span class="result-score">相似度: %</span>
                    </div>
                    <div class="result-content"></div>
                </div>
            ).join('');

        } catch (e) {
            ragResults.innerHTML = '<p style="color: #ef4444">检索失败: ' + e.message + '</p>';
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ====== 启动 ======
    init();
})();
