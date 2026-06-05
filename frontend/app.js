// ============================================================
// Agent_CUG — ChatGPT 风格前端 JS
// ============================================================

(function () {
    'use strict';

    // ====== DOM ======
    const $ = (id) => document.getElementById(id);
    const sidebar = $('sidebar');
    const toggleSidebarBtn = $('toggleSidebarBtn');
    const openSidebarBtn = $('openSidebarBtn');
    const newChatBtn = $('newChatBtn');
    const chatMessages = $('chatMessages');
    const welcomeScreen = $('welcomeScreen');
    const messageInput = $('messageInput');
    const sendBtn = $('sendBtn');
    const uploadBtn = $('uploadBtn');
    const fileInput = $('fileInput');
    const historyList = $('historyList');
    const modelBadge = $('modelBadge');
    const navItems = document.querySelectorAll('.sidebar-nav-item');
    const chatPanel = $('chatPanel');
    const ragPanel = $('ragPanel');
    const settingsPanel = $('settingsPanel');
    const uploadDropzone = $('uploadDropzone');
    const ragFileInput = $('ragFileInput');
    const uploadStatus = $('uploadStatus');
    const ragQueryInput = $('ragQueryInput');
    const ragQueryBtn = $('ragQueryBtn');
    const ragResults = $('ragResults');
    const docCountEl = $('docCount');

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
            setText('settingProvider', config.model_provider);
            setText('settingModel', config.llm_model);
            setText('settingEmbedding', config.embedding_model);
            setText('settingDocCount', config.rag_document_count);
            if (docCountEl) docCountEl.textContent = '文档: ' + (config.rag_document_count || 0);
        } catch (e) { console.warn('配置加载失败:', e); }
    }

    function setText(id, val) { const el = $(id); if (el && val != null) el.textContent = val; }

    async function loadHistory() {
        try {
            const resp = await fetch('/api/history');
            const data = await resp.json();
            conversations = data.conversations || [];
            renderHistory();
        } catch (e) { console.warn('历史加载失败:', e); }
    }

    function renderHistory() {
        if (!historyList) return;
        if (conversations.length === 0) {
            historyList.innerHTML = '<div class="history-empty">暂无会话记录</div>';
            return;
        }
        historyList.innerHTML = conversations.map(function (conv) {
            var active = conv.id === conversationId ? ' active' : '';
            var time = formatTime(conv.created_at);
            return '<div class="history-item' + active + '" data-id="' + conv.id + '" title="' + escAttr(conv.title) + '">' +
                '<span class="history-title">' + escHtml(conv.title) + '</span>' +
                '<span class="history-time">' + time + '</span></div>';
        }).join('');
        historyList.querySelectorAll('.history-item').forEach(function (item) {
            item.addEventListener('click', function () {
                conversationId = item.dataset.id;
                renderHistory();
            });
        });
    }

    function formatTime(isoStr) {
        if (!isoStr) return '';
        try {
            var d = new Date(isoStr), now = new Date(), diff = now - d;
            if (diff < 60000) return '刚刚';
            if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
            if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
            return d.toLocaleDateString('zh-CN');
        } catch (e) { return ''; }
    }

    // ====== 事件 ======
    function setupEventListeners() {
        toggleSidebarBtn.addEventListener('click', function () {
            sidebar.classList.toggle('collapsed');
            openSidebarBtn.style.display = sidebar.classList.contains('collapsed') ? 'flex' : 'none';
        });
        openSidebarBtn.addEventListener('click', function () {
            sidebar.classList.remove('collapsed');
            openSidebarBtn.style.display = 'none';
        });
        navItems.forEach(function (item) {
            item.addEventListener('click', function (e) {
                e.preventDefault();
                switchPanel(item.dataset.panel);
                navItems.forEach(function (n) { n.classList.remove('active'); });
                item.classList.add('active');
            });
        });
        newChatBtn.addEventListener('click', startNewChat);
        sendBtn.addEventListener('click', sendMessage);
        messageInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
        });
        uploadBtn.addEventListener('click', function () { fileInput.click(); });
        fileInput.addEventListener('change', handleFileUpload);
        document.querySelectorAll('.chip').forEach(function (chip) {
            chip.addEventListener('click', function () {
                var p = chip.dataset.prompt;
                if (p) { messageInput.value = p; sendMessage(); }
            });
        });
        uploadDropzone.addEventListener('click', function () { ragFileInput.click(); });
        uploadDropzone.addEventListener('dragover', function (e) { e.preventDefault(); uploadDropzone.classList.add('dragover'); });
        uploadDropzone.addEventListener('dragleave', function () { uploadDropzone.classList.remove('dragover'); });
        uploadDropzone.addEventListener('drop', function (e) { e.preventDefault(); uploadDropzone.classList.remove('dragover'); handleRagFiles(e.dataTransfer.files); });
        ragFileInput.addEventListener('change', function (e) { handleRagFiles(e.target.files); });
        ragQueryBtn.addEventListener('click', doRagQuery);
        ragQueryInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') doRagQuery(); });
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

    // ====== 新对话 ======
    function startNewChat() {
        conversationId = null;
        messages = [];
        chatMessages.querySelectorAll('.message-row').forEach(function (el) { el.remove(); });
        if (welcomeScreen) {
            welcomeScreen.style.display = 'flex';
            if (!welcomeScreen.parentNode) chatMessages.appendChild(welcomeScreen);
        }
        messageInput.value = '';
        messageInput.focus();
        renderHistory();
    }

    // ====== 发送消息 ======
    async function sendMessage() {
        var text = messageInput.value.trim();
        if (!text || isStreaming) return;

        isStreaming = true;
        sendBtn.disabled = true;
        if (welcomeScreen) welcomeScreen.style.display = 'none';

        addMessage('user', text);
        messages.push({ role: 'user', content: text });
        messageInput.value = '';
        messageInput.style.height = 'auto';

        var assistantRow = addMessage('assistant', '', true);
        var contentEl = assistantRow.querySelector('.message-content');
        var fullText = '';

        // 检测是否有思考过程标记
        var thinkingBuffer = '';
        var mainBuffer = '';
        var inThinking = false;
        var thinkingStart = '【思考】' || '【推理】';
        var thinkingEnd = '【回答】';

        try {
            var response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, conversation_id: conversationId }),
            });
            if (!response.ok) {
                var errData = await response.json().catch(function () { return {}; });
                throw new Error(errData.detail || '请求失败: ' + response.status);
            }

            var reader = response.body.getReader();
            var decoder = new TextDecoder();
            var buffer = '';
            var currentEvent = null;
            var currentData = '';

            while (true) {
                var chunk = await reader.read();
                if (chunk.done) break;

                buffer += decoder.decode(chunk.value, { stream: true });
                var lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i];
                    if (line.startsWith('event: ')) {
                        currentEvent = line.slice(7).trim();
                    } else if (line.startsWith('data: ')) {
                        currentData = line.slice(6);
                    } else if (line === '' && currentEvent && currentData) {
                        handleSSE(currentEvent, currentData);
                        currentEvent = null;
                        currentData = '';
                    }
                }
                if (currentEvent && currentData) {
                    handleSSE(currentEvent, currentData);
                }
            }

            function handleSSE(event, data) {
                if (event === 'token') {
                    fullText += data;
                    renderStreamingContent(contentEl, fullText);
                    scrollToBottom();
                } else if (event === 'done') {
                    try {
                        var payload = JSON.parse(data);
                        conversationId = payload.conversation_id;
                        renderFinalContent(contentEl, fullText);
                    } catch (e) {
                        renderFinalContent(contentEl, fullText);
                    }
                } else if (event === 'error') {
                    contentEl.innerHTML = '<p style="color:#ef4444">错误: ' + escHtml(data) + '</p>';
                }
            }

            renderFinalContent(contentEl, fullText);
            messages.push({ role: 'assistant', content: fullText });
            loadHistory();

        } catch (error) {
            contentEl.innerHTML = '<p style="color:#ef4444">网络错误: ' + escHtml(error.message) + '</p>';
        }

        isStreaming = false;
        sendBtn.disabled = false;
        messageInput.focus();
        scrollToBottom();
    }

    function addMessage(role, content, streaming) {
        var row = document.createElement('div');
        row.className = 'message-row ' + role;

        var inner = document.createElement('div');
        inner.className = 'message-inner';

        var avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = role === 'user' ? '👤' : role === 'tool' ? '🔧' : '🤖';

        var contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        if (streaming) contentDiv.classList.add('streaming-cursor');
        if (content) contentDiv.innerHTML = renderMarkdown(content);

        inner.appendChild(avatar);
        inner.appendChild(contentDiv);
        row.appendChild(inner);
        chatMessages.appendChild(row);
        scrollToBottom();
        return row;
    }

    function renderStreamingContent(el, text) {
        // 检测思考标记
        var thinkMatch = text.match(/【思考】(.*?)(?:【回答】|$)/s);
        var hasThinkStart = text.indexOf('【思考】') !== -1;
        var hasThinkEnd = text.indexOf('【回答】') !== -1;

        var html = '';
        if (hasThinkStart) {
            var thinkContent = '';
            var answerContent = '';
            if (thinkMatch) {
                thinkContent = thinkMatch[1];
            }
            if (hasThinkEnd) {
                answerContent = text.split('【回答】').slice(1).join('【回答】');
            }
            // 思考部分（折叠）
            if (thinkContent.trim()) {
                html += '<div class="thinking-section open">' +
                    '<div class="thinking-header" onclick="this.parentElement.classList.toggle(\'open\')">' +
                    '💭 思考过程 <span class="toggle-icon">▶</span></div>' +
                    '<div class="thinking-body">' + renderMarkdown(thinkContent) + '</div></div>';
            }
            // 回答部分
            if (answerContent) {
                html += renderMarkdown(answerContent);
            }
        } else {
            html = renderMarkdown(text);
        }
        el.innerHTML = html;
        el.classList.add('streaming-cursor');
    }

    function renderFinalContent(el, text) {
        el.classList.remove('streaming-cursor');
        el.innerHTML = renderContentWithThinking(text);
        // 绑定代码块复制按钮
        el.querySelectorAll('.copy-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var code = btn.dataset.code;
                copyToClipboard(code).then(function () {
                    btn.textContent = '✓ 已复制';
                    btn.classList.add('copied');
                    setTimeout(function () { btn.textContent = '复制'; btn.classList.remove('copied'); }, 2000);
                });
            });
        });
    }

    function renderContentWithThinking(text) {
        // 检测思考标记
        var thinkMatch = text.match(/【思考】(.*?)(?:【回答】|$)/s);
        var hasThinkStart = text.indexOf('【思考】') !== -1;
        var hasThinkEnd = text.indexOf('【回答】') !== -1;

        if (!hasThinkStart) return renderMarkdown(text);

        var thinkContent = thinkMatch ? thinkMatch[1] : '';
        var answerContent = hasThinkEnd ? text.split('【回答】').slice(1).join('【回答】') : '';

        var html = '';
        if (thinkContent.trim()) {
            html += '<div class="thinking-section">' +
                '<div class="thinking-header" onclick="this.parentElement.classList.toggle(\'open\')">' +
                '💭 思考过程 <span class="toggle-icon">▶</span></div>' +
                '<div class="thinking-body">' + renderMarkdown(thinkContent) + '</div></div>';
        }
        if (answerContent) html += renderMarkdown(answerContent);
        return html || renderMarkdown(text);
    }

    // ====== Markdown 渲染 ======
    function renderMarkdown(text) {
        if (!text) return '';
        var html = escHtml(text);

        // 代码块 ```lang\n...\n```
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (match, lang, code) {
            var langLabel = lang || 'code';
            return '<div class="code-block-header">' +
                '<span>' + escHtml(langLabel) + '</span>' +
                '<button class="copy-btn" data-code="' + escAttr(code.trim()) + '">复制</button></div>' +
                '<pre><code>' + escHtml(code) + '</code></pre>';
        });

        // 行内代码 `...`
        html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');

        // 标题
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

        // 粗体 **...**
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        // 斜体 *...*
        html = html.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '<em>$1</em>');

        // 链接 [text](url)
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

        // 无序列表
        html = html.replace(/^[\*\-] (.+)$/gm, '<li>$1</li>');
        html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

        // 有序列表
        html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

        // 引用
        html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

        // 分隔线
        html = html.replace(/^---$/gm, '<hr>');

        // 换行
        var paragraphs = html.split('\n\n');
        html = paragraphs.map(function (p) {
            p = p.trim();
            if (!p) return '';
            if (p.startsWith('<h') || p.startsWith('<pre') || p.startsWith('<div') ||
                p.startsWith('<ul') || p.startsWith('<ol') || p.startsWith('<blockquote') ||
                p.startsWith('<hr') || p.startsWith('<table')) return p;
            return '<p>' + p.replace(/\n/g, '<br>') + '</p>';
        }).join('\n');

        return html;
    }

    function scrollToBottom() {
        requestAnimationFrame(function () {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    // ====== 剪贴板 ======
    async function copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
        } catch (e) {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed'; ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        }
    }

    // ====== 文件上传 ======
    async function handleFileUpload(e) {
        var files = e.target.files;
        if (!files.length) return;
        for (var i = 0; i < files.length; i++) await uploadFile(files[i]);
        fileInput.value = '';
        refreshDocCount();
    }

    async function handleRagFiles(files) {
        if (!files.length) return;
        for (var i = 0; i < files.length; i++) {
            showUploadStatus('info', '⏳ 正在处理 ' + files[i].name + '...');
            await uploadFile(files[i]);
        }
        ragFileInput.value = '';
        refreshDocCount();
    }

    async function uploadFile(file) {
        try {
            var formData = new FormData();
            formData.append('file', file);
            var resp = await fetch('/api/rag/upload', { method: 'POST', body: formData });
            var result = await resp.json();
            if (resp.ok) {
                showUploadStatus('success', '✅ ' + file.name + ' — ' + result.chunks + ' 个分块已导入');
            } else {
                showUploadStatus('error', '❌ ' + file.name + ' — ' + (result.detail || '上传失败'));
            }
        } catch (e) { showUploadStatus('error', '❌ ' + file.name + ' — 网络错误'); }
    }

    function showUploadStatus(type, message) {
        if (!uploadStatus) return;
        var el = document.createElement('div');
        el.className = type;
        el.textContent = message;
        uploadStatus.appendChild(el);
        setTimeout(function () { el.remove(); }, 5000);
    }

    async function refreshDocCount() {
        try {
            var resp = await fetch('/api/health');
            var data = await resp.json();
            if (docCountEl) docCountEl.textContent = '文档: ' + (data.document_count || 0);
            setText('settingDocCount', data.document_count);
        } catch (e) {}
    }

    // ====== RAG 检索 ======
    async function doRagQuery() {
        var query = ragQueryInput.value.trim();
        if (!query) return;
        ragResults.innerHTML = '<p style="color:var(--text-tertiary)">检索中...</p>';
        try {
            var resp = await fetch('/api/rag/query', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query, top_k: 5 }),
            });
            var data = await resp.json();
            if (!data.documents || data.documents.length === 0) {
                ragResults.innerHTML = '<p style="color:var(--text-tertiary)">未找到相关文档</p>';
                return;
            }
            ragResults.innerHTML = data.documents.map(function (doc, i) {
                return '<div class="rag-result-item"><div class="result-header">' +
                    '<span>📄 ' + escHtml(doc.source || '未知') + '</span>' +
                    '<span class="result-score">相似度: ' + (doc.score * 100).toFixed(1) + '%</span></div>' +
                    '<div class="result-content">' + escHtml(doc.content) + '</div></div>';
            }).join('');
        } catch (e) { ragResults.innerHTML = '<p style="color:#ef4444">检索失败: ' + e.message + '</p>'; }
    }

    // ====== 工具 ======
    function escHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function escAttr(text) {
        return String(text).replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // ====== 启动 ======
    init();
})();