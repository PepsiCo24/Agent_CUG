// ============================================================
// Agent_CUG — ChatGPT 风格前端 JS
// ============================================================

(function () {
    "use strict";

    // ====== DOM ======
    var sidebar = document.getElementById("sidebar");
    var toggleSidebarBtn = document.getElementById("toggleSidebarBtn");
    var openSidebarBtn = document.getElementById("openSidebarBtn");
    var newChatBtn = document.getElementById("newChatBtn");
    var chatMessages = document.getElementById("chatMessages");
    var welcomeScreen = document.getElementById("welcomeScreen");
    var messageInput = document.getElementById("messageInput");
    var sendBtn = document.getElementById("sendBtn");
    var uploadBtn = document.getElementById("uploadBtn");
    var fileInput = document.getElementById("fileInput");
    var historyList = document.getElementById("historyList");
    var modelBadge = document.getElementById("modelBadge");
    var navItems = document.querySelectorAll(".sidebar-nav-item");
    var chatPanel = document.getElementById("chatPanel");
    var ragPanel = document.getElementById("ragPanel");
    var settingsPanel = document.getElementById("settingsPanel");
    var uploadDropzone = document.getElementById("uploadDropzone");
    var ragFileInput = document.getElementById("ragFileInput");
    var uploadStatus = document.getElementById("uploadStatus");
    var ragQueryInput = document.getElementById("ragQueryInput");
    var ragQueryBtn = document.getElementById("ragQueryBtn");
    var ragResults = document.getElementById("ragResults");
    var docCountEl = document.getElementById("docCount");

    // ====== 状态 ======
    var conversationId = null;
    var isStreaming = false;
    var messages = [];
    var conversations = [];

    
    // ====== 暗色模式检测 ======
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
    if (prefersDark.matches) document.body.classList.add("dark-mode");
    prefersDark.addEventListener("change", function(e) {
        document.body.classList.toggle("dark-mode", e.matches);
    });

    // ====== 初始化 ======
    function init() {
        loadConfig();
        loadHistory();
        setupEventListeners();
        autoResizeInput();
    }

    async function loadConfig() {
        try {
            var resp = await fetch("/api/config");
            var config = await resp.json();
            if (modelBadge) modelBadge.textContent = config.llm_model || "mimo-v2.5-pro";
            setText("settingProvider", config.model_provider);
            setText("settingModel", config.llm_model);
            setText("settingEmbedding", config.embedding_model);
            setText("settingDocCount", config.rag_document_count);
            if (docCountEl) docCountEl.textContent = "\u6587\u6863: " + (config.rag_document_count || 0);
        } catch (e) { console.warn("\u914d\u7f6e\u52a0\u8f7d\u5931\u8d25:", e); }
    }

    function setText(id, val) { var el = document.getElementById(id); if (el && val != null) el.textContent = val; }

    async function loadHistory() {
        try {
            var resp = await fetch("/api/history");
            var data = await resp.json();
            conversations = data.conversations || [];
            renderHistory();
        } catch (e) { console.warn("\u5386\u53f2\u52a0\u8f7d\u5931\u8d25:", e); }
    }

    function renderHistory() {
        if (!historyList) return;
        if (conversations.length === 0) {
            historyList.innerHTML = "<div class=\"history-empty\">暂无会话记录</div>";
            return;
        }
        var html = "";
        for (var i = 0; i < conversations.length; i++) {
            var conv = conversations[i];
            var active = conv.id === conversationId ? " active" : "";
            html += "<div class=\"history-item" + active + "\" data-id=\"" + conv.id + "\">" +
                "<div class=\"history-item-main\">" +
                "<span class=\"history-title\">" + escHtml(conv.title) + "</span>" +
                "<span class=\"history-time\">" + formatTime(conv.created_at) + "</span>" +
                "</div>" +
                "<div class=\"history-actions\">" +
                "<button class=\"history-action-btn\" data-action=\"rename\" title=\"重命名\">" +
                "<svg width=\"14\" height=\"14\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\">" +
                "<path d=\"M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7\"></path>" +
                "<path d=\"M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z\"></path></svg></button>" +
                "<button class=\"history-action-btn\" data-action=\"delete\" title=\"删除\">" +
                "<svg width=\"14\" height=\"14\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\">" +
                "<polyline points=\"3 6 5 6 21 6\"></polyline>" +
                "<path d=\"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2\"></path></svg></button>" +
                "</div></div>";
        }
        historyList.innerHTML = html;
        var items = historyList.querySelectorAll(".history-item");
        for (var j = 0; j < items.length; j++) {
            items[j].addEventListener("click", function (e) {
                if (e.target.closest(".history-action-btn")) return;
                var convId = this.dataset.id;
                conversationId = convId;
                loadConversation(convId);
                renderHistory();
            });
            var btns = items[j].querySelectorAll(".history-action-btn");
            for (var k = 0; k < btns.length; k++) {
                btns[k].addEventListener("click", function (ev) {
                    ev.stopPropagation();
                    var cid = this.parentElement.parentElement.dataset.id;
                    var action = this.dataset.action;
                    if (action === "delete") deleteConversation(cid);
                    else if (action === "rename") renameConversation(cid);
                });
            }
        }
    }
    function formatTime(isoStr) {
        if (!isoStr) return "";
        try {
            var d = new Date(isoStr), now = new Date(), diff = now - d;
            if (diff < 60000) return "\u521a\u521a";
            if (diff < 3600000) return Math.floor(diff / 60000) + "\u5206\u949f\u524d";
            if (diff < 86400000) return Math.floor(diff / 3600000) + "\u5c0f\u65f6\u524d";
            return d.toLocaleDateString("zh-CN");
        } catch (e) { return ""; }
    }

    // ====== 事件 ======
    function setupEventListeners() {
        toggleSidebarBtn.addEventListener("click", function () {
            sidebar.classList.toggle("collapsed");
            openSidebarBtn.style.display = sidebar.classList.contains("collapsed") ? "flex" : "none";
        });
        openSidebarBtn.addEventListener("click", function () {
            sidebar.classList.remove("collapsed");
            openSidebarBtn.style.display = "none";
        });
        for (var i = 0; i < navItems.length; i++) {
            navItems[i].addEventListener("click", function (e) {
                e.preventDefault();
                switchPanel(this.dataset.panel);
                for (var j = 0; j < navItems.length; j++) navItems[j].classList.remove("active");
                this.classList.add("active");
            });
        }
        newChatBtn.addEventListener("click", startNewChat);
        sendBtn.addEventListener("click", sendMessage);
        messageInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
        });
        uploadBtn.addEventListener("click", function () { fileInput.click(); });
        fileInput.addEventListener("change", handleFileUpload);
        var chips = document.querySelectorAll(".chip");
        for (var k = 0; k < chips.length; k++) {
            chips[k].addEventListener("click", function () {
                var p = this.dataset.prompt;
                if (p) { messageInput.value = p; sendMessage(); }
            });
        }
        uploadDropzone.addEventListener("click", function () { ragFileInput.click(); });
        uploadDropzone.addEventListener("dragover", function (e) { e.preventDefault(); uploadDropzone.classList.add("dragover"); });
        uploadDropzone.addEventListener("dragleave", function () { uploadDropzone.classList.remove("dragover"); });
        uploadDropzone.addEventListener("drop", function (e) { e.preventDefault(); uploadDropzone.classList.remove("dragover"); handleRagFiles(e.dataTransfer.files); });
        ragFileInput.addEventListener("change", function (e) { handleRagFiles(e.target.files); });
        ragQueryBtn.addEventListener("click", doRagQuery);
        ragQueryInput.addEventListener("keydown", function (e) { if (e.key === "Enter") doRagQuery(); });
        messageInput.addEventListener("input", autoResizeInput);

        // 代理：思考面板折叠
        document.addEventListener("click", function (e) {
            var header = e.target.closest(".thinking-header");
            if (header) {
                var section = header.parentElement;
                if (section) section.classList.toggle("open");
            }
        });

        // 代理：代码复制按钮
        document.addEventListener("click", function (e) {
            var btn = e.target.closest(".copy-btn");
            if (btn) {
                var code = btn.dataset.code || "";
                copyToClipboard(code).then(function () {
                    btn.textContent = "\u2713 \u5df2\u590d\u5236";
                    btn.classList.add("copied");
                    setTimeout(function () { btn.textContent = "\u590d\u5236"; btn.classList.remove("copied"); }, 2000);
                });
            }
        });
    }

        // ==== 右键菜单 ====
        document.addEventListener("contextmenu", function (e) {
            var item = e.target.closest(".history-item");
            if (!item) return;
            e.preventDefault();
            var cid = item.dataset.id;
            if (!cid) return;
            var existing = document.querySelector(".context-menu");
            if (existing) existing.remove();
            var menu = document.createElement("div");
            menu.className = "context-menu";
            menu.style.left = e.pageX + "px";
            menu.style.top = e.pageY + "px";
            menu.innerHTML = '<div class="context-menu-item" data-action="rename">\u270f\ufe0f 重命名</div>' +'<div class="context-menu-item danger" data-action="delete">\ud83d\uddd1\ufe0f 删除</div>';
            menu.querySelector("[data-action=rename]").addEventListener("click", function () {
                menu.remove(); renameConversation(cid);
            });
            menu.querySelector("[data-action=delete]").addEventListener("click", function () {
                menu.remove(); deleteConversation(cid);
            });
            document.body.appendChild(menu);
        });
        document.addEventListener("click", function () {
            var menu = document.querySelector(".context-menu");
            if (menu) menu.remove();
        });

    function switchPanel(panel) {
        chatPanel.classList.remove("active");
        ragPanel.classList.remove("active");
        settingsPanel.classList.remove("active");
        if (panel === "chat") chatPanel.classList.add("active");
        else if (panel === "rag") { ragPanel.classList.add("active"); refreshDocCount(); }
        else if (panel === "settings") { settingsPanel.classList.add("active"); loadConfig(); }
    }

    function autoResizeInput() {
        messageInput.style.height = "auto";
        messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + "px";
    }

    // ====== 新对话 ======
    function startNewChat() {
        // ???????
        switchPanel("chat");
        // ??????
        for (var j = 0; j < navItems.length; j++) {
            navItems[j].classList.remove("active");
            if (navItems[j].dataset.panel === "chat") navItems[j].classList.add("active");
        }
        conversationId = null;
        messages = [];
        var rows = chatMessages.querySelectorAll(".message-row");
        for (var i = 0; i < rows.length; i++) rows[i].remove();
        if (welcomeScreen) {
            welcomeScreen.style.display = "flex";
            if (!welcomeScreen.parentNode) chatMessages.appendChild(welcomeScreen);
        }
        messageInput.value = "";
        messageInput.focus();
        loadHistory();
    }

    // ====== ???? ======
    async function loadConversation(convId) {
        if (!convId) return;
        try {
            var resp = await fetch("/api/history/" + convId);
            if (!resp.ok) throw new Error("?????");
            var data = await resp.json();
            messages = data.messages || [];

            // ????????
            var rows = chatMessages.querySelectorAll(".message-row");
            for (var i = 0; i < rows.length; i++) rows[i].remove();

            // ?????
            if (welcomeScreen) welcomeScreen.style.display = "none";

            // ??????
            for (var i = 0; i < messages.length; i++) {
                var msg = messages[i];
                addMessage(msg.role, msg.content);
            }
            scrollToBottom();
        } catch (e) {
            console.warn("??????:", e);
        }
    }

    // ====== ???? ======
    // ====== 删除对话 ======
    async function deleteConversation(convId) {
        if (!convId) return;
        if (!confirm("确定要删除这个对话吗？")) return;
        try {
            var resp = await fetch("/api/history/" + convId, { method: "DELETE" });
            if (resp.ok) {
                if (conversationId === convId) startNewChat();
                loadHistory();
            }
        } catch (e) { console.warn("删除失败:", e); }
    }

    // ====== 重命名对话 ======
    async function renameConversation(convId) {
        if (!convId) return;
        var newTitle = prompt("请输入新标题:");
        if (!newTitle || !newTitle.trim()) return;
        try {
            var resp = await fetch("/api/history/" + convId + "/title", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: newTitle.trim() }),
            });
            if (resp.ok) loadHistory();
        } catch (e) { console.warn("重命名失败:", e); }
    }


    async function sendMessage() {
        var text = messageInput.value.trim();
        if (!text || isStreaming) return;

        isStreaming = true;
        sendBtn.disabled = true;
        if (welcomeScreen) welcomeScreen.style.display = "none";

        addMessage("user", text);
        messages.push({ role: "user", content: text });
        messageInput.value = "";
        messageInput.style.height = "auto";

        var assistantRow = addMessage("assistant", "", true);
        var contentEl = assistantRow.querySelector(".message-content");
        var toolCallEl = null;
        var fullText = "";
        var toolCalls = [];

        try {
            var response = await fetch("/api/chat/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text, conversation_id: conversationId }),
            });
            if (!response.ok) {
                var errData = await response.json().catch(function () { return {}; });
                throw new Error(errData.detail || "\u8bf7\u6c42\u5931\u8d25: " + response.status);
            }

            var reader = response.body.getReader();
            var decoder = new TextDecoder();
            var buffer = "";

            while (true) {
                var chunk = await reader.read();
                if (chunk.done) break;
                buffer += decoder.decode(chunk.value, { stream: true });
                var lines = buffer.split("\n");
                buffer = lines.pop() || "";

                var currentEvent = null, currentData = "";
                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i];
                    if (line.startsWith("event: ")) {
                        currentEvent = line.slice(7).trim();
                        currentData = "";
                    } else if (line.startsWith("data: ")) {
                        currentData = line.slice(6);
                    } else if (line === "" && currentEvent) {
                        processEvent(currentEvent, currentData);
                        currentEvent = null;
                    }
                }
                if (currentEvent) processEvent(currentEvent, currentData);
                if (contentEl) renderStreamingContent(contentEl, fullText, toolCalls);
                scrollToBottom();
            }

            function processEvent(event, data) {
                if (event === "token") {
                    fullText += data;
                } else if (event === "tool_call") {
                    try { toolCalls.push(JSON.parse(data)); } catch (e) {}
                } else if (event === "done") {
                    try {
                        var payload = JSON.parse(data);
                        conversationId = payload.conversation_id;
                    } catch (e) {}
                } else if (event === "error") {
                    contentEl.innerHTML = "<p style=\"color:#ef4444\">\u9519\u8bef: " + escHtml(data) + "</p>";
                }
            }

            if (contentEl) {
                contentEl.classList.remove("streaming-cursor");
                contentEl.innerHTML = renderFinal(fullText, toolCalls);
            }
            messages.push({ role: "assistant", content: fullText });
            loadHistory();

        } catch (error) {
            if (contentEl) {
                contentEl.classList.remove("streaming-cursor");
                contentEl.innerHTML = "<p style=\"color:#ef4444\">\u7f51\u7edc\u9519\u8bef: " + escHtml(error.message) + "</p>";
            }
        }

        isStreaming = false;
        sendBtn.disabled = false;
        messageInput.focus();

    // ====== 键盘快捷键 ======
    messageInput.addEventListener("keydown", function(e) {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            sendMessage();
        }
    });

        scrollToBottom();
    }

    function addMessage(role, content, streaming) {
        var row = document.createElement("div");
        row.className = "message-row " + role;
        var inner = document.createElement("div");
        inner.className = "message-inner";
        var avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.textContent = role === "user" ? "\ud83d\udc64" : role === "tool" ? "\ud83d\udd27" : "\ud83e\udd16";
        var contentDiv = document.createElement("div");
        contentDiv.className = "message-content";
        if (streaming) contentDiv.classList.add("streaming-cursor");
        if (content) contentDiv.innerHTML = renderMarkdown(content);
        inner.appendChild(avatar);
        inner.appendChild(contentDiv);
        row.appendChild(inner);
        chatMessages.appendChild(row);
        scrollToBottom();
        return row;
    }

    // ====== 渲染 ======
    function renderStreamingContent(el, text, toolCalls) {
        var html = "";
        if (toolCalls && toolCalls.length > 0) {
            for (var i = 0; i < toolCalls.length; i++) {
                html += "<div class=\"tool-call-display\">" +
                    "<div class=\"tool-name\">\ud83d\udd27 " + escHtml(toolCalls[i].name || "tool") + "</div>" +
                    "<div class=\"tool-result\">" + escHtml(String(toolCalls[i].result || "")) + "</div></div>";
            }
        }
        html += renderContentWithThinking(text);
        el.innerHTML = html;
        el.classList.add("streaming-cursor");
    }

    function renderFinal(text, toolCalls) {
        var html = "";
        if (toolCalls && toolCalls.length > 0) {
            for (var i = 0; i < toolCalls.length; i++) {
                html += "<div class=\"tool-call-display\">" +
                    "<div class=\"tool-name\">\ud83d\udd27 " + escHtml(toolCalls[i].name || "tool") + "</div>" +
                    "<div class=\"tool-result\">" + escHtml(String(toolCalls[i].result || "")) + "</div></div>";
            }
        }
        html += renderContentWithThinking(text);
        return html;
    }

    function renderContentWithThinking(text) {
        if (!text) return "";
        var thinkIdx = text.indexOf("\u3010\u601d\u8003\u3011");
        var answerIdx = text.indexOf("\u3010\u56de\u7b54\u3011");

        if (thinkIdx === -1) return renderMarkdown(text);

        var thinkContent = "";
        var answerContent = "";

        if (answerIdx > thinkIdx) {
            thinkContent = text.substring(thinkIdx + 4, answerIdx).trim();
            answerContent = text.substring(answerIdx + 4).trim();
        } else {
            thinkContent = text.substring(thinkIdx + 4).trim();
        }

        var html = "";
        if (thinkContent) {
            html += "<div class=\"thinking-section\">" +
                "<div class=\"thinking-header\">\ud83d\udcad \u601d\u8003\u8fc7\u7a0b <span class=\"toggle-icon\">\u25b6</span></div>" +
                "<div class=\"thinking-body\">" + renderMarkdown(thinkContent) + "</div></div>";
        }
        if (answerContent) {
            html += renderMarkdown(answerContent);
        }
        return html || renderMarkdown(text);
    }

    // ====== Markdown 渲染 ======
    function renderMarkdown(text) {
        if (!text) return "";

        // 1. Extract and protect code blocks first
        var codeBlocks = [];
        var html = text.replace(/```(\w*)\n([\s\S]*?)```/g, function (match, lang, code) {
            codeBlocks.push({ lang: lang || "code", code: code.trim() });
            return "%%CODEBLOCK_" + (codeBlocks.length - 1) + "%%";
        });

        // 2. Escape HTML (but not in code blocks)
        html = escHtml(html);

        // 3. Restore code blocks with proper HTML
        html = html.replace(/%%CODEBLOCK_(\d+)%%/g, function (match, idx) {
            var block = codeBlocks[parseInt(idx)];
            return '<div class="code-block-header"><span>' + escHtml(block.lang) +
                '</span><button class="copy-btn" data-code="' + escAttr(block.code) + '">复制</button></div>' +
                '<pre><code>' + escHtml(block.code) + '</code></pre>';
        });

        // 4. Inline code
        html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');

        // 5. Headers
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

        // 6. Bold and italic
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');

        // 7. Links
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

        // 8. Images
        html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%">');

        // 9. Unordered lists
        html = html.replace(/^[\*\-] (.+)$/gm, '<li>$1</li>');
        html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

        // 10. Ordered lists
        html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

        // 11. Blockquote
        html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

        // 12. Horizontal rule
        html = html.replace(/^---$/gm, '<hr>');

        // 13. Table support
        html = html.replace(/^\|(.+)\|$/gm, function (match) {
            var cells = match.split('|').filter(function (c) { return c.trim(); });
            if (cells.length < 2) return match;
            var row = '<tr>';
            for (var i = 0; i < cells.length; i++) {
                row += '<td>' + cells[i].trim() + '</td>';
            }
            return row + '</tr>';
        });
        html = html.replace(/((?:<tr>.*<\/tr>\n?)+)/g, '<table>$1</table>');

        // 14. Paragraph wrapping
        var paragraphs = html.split('\n\n');
        html = '';
        for (var p = 0; p < paragraphs.length; p++) {
            var para = paragraphs[p].trim();
            if (!para) continue;
            if (para.indexOf('<h') === 0 || para.indexOf('<pre') === 0 || para.indexOf('<div') === 0 ||
                para.indexOf('<ul') === 0 || para.indexOf('<ol') === 0 || para.indexOf('<blockquote') === 0 ||
                para.indexOf('<hr') === 0 || para.indexOf('<tr') === 0 || para.indexOf('<table') === 0) {
                html += para + '\n';
            } else {
                html += '<p>' + para.replace(/\n/g, '<br>') + '</p>\n';
            }
        }
        return html;
    }    function scrollToBottom() {
        requestAnimationFrame(function () {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    // ====== 剪贴板 ======
    async function copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
        } catch (e) {
            var ta = document.createElement("textarea");
            ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
            document.body.appendChild(ta); ta.select();
            document.execCommand("copy"); document.body.removeChild(ta);
        }
    }

    // ====== 文件上传 ======
    async function handleFileUpload(e) {
        var files = e.target.files;
        if (!files.length) return;
        for (var i = 0; i < files.length; i++) await uploadFile(files[i]);
        fileInput.value = ""; refreshDocCount();
    }

    async function handleRagFiles(files) {
        if (!files.length) return;
        for (var i = 0; i < files.length; i++) {
            showUploadStatus("info", "\u23f3 \u6b63\u5728\u5904\u7406 " + files[i].name + "...");
            await uploadFile(files[i]);
        }
        ragFileInput.value = ""; refreshDocCount();
    }

    async function uploadFile(file) {
        try {
            var formData = new FormData();
            formData.append("file", file);
            var resp = await fetch("/api/rag/upload", { method: "POST", body: formData });
            var result = await resp.json();
            showUploadStatus(resp.ok ? "success" : "error",
                (resp.ok ? "\u2705 " : "\u274c ") + file.name + " \u2014 " + (result.chunks || 0) + " \u4e2a\u5206\u5757" +
                (resp.ok ? "\u5df2\u5bfc\u5165" : " \u4e0a\u4f20\u5931\u8d25: " + (result.detail || "")));
        } catch (e) { showUploadStatus("error", "\u274c " + file.name + " \u2014 \u7f51\u7edc\u9519\u8bef"); }
    }

    function showUploadStatus(type, message) {
        if (!uploadStatus) return;
        var el = document.createElement("div");
        el.className = type; el.textContent = message;
        uploadStatus.appendChild(el);
        setTimeout(function () { el.remove(); }, 5000);
    }

    async function refreshDocCount() {
        try {
            var resp = await fetch("/api/health");
            var data = await resp.json();
            if (docCountEl) docCountEl.textContent = "\u6587\u6863: " + (data.document_count || 0);
            setText("settingDocCount", data.document_count);
        } catch (e) {}
    }

    // ====== RAG 检索 ======
    async function doRagQuery() {
        var query = ragQueryInput.value.trim();
        if (!query) return;
        ragResults.innerHTML = "<p style=\"color:var(--text-tertiary)\">\u68c0\u7d22\u4e2d...</p>";
        try {
            var resp = await fetch("/api/rag/query", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: query, top_k: 5 }),
            });
            var data = await resp.json();
            if (!data.documents || data.documents.length === 0) {
                ragResults.innerHTML = "<p style=\"color:var(--text-tertiary)\">\u672a\u627e\u5230\u76f8\u5173\u6587\u6863</p>";
                return;
            }
            var html = "";
            for (var i = 0; i < data.documents.length; i++) {
                var doc = data.documents[i];
                html += "<div class=\"rag-result-item\"><div class=\"result-header\">" +
                    "<span>\ud83d\udcc4 " + escHtml(doc.source || "\u672a\u77e5") + "</span>" +
                    "<span class=\"result-score\">\u76f8\u4f3c\u5ea6: " + (doc.score * 100).toFixed(1) + "%</span></div>" +
                    "<div class=\"result-content\">" + escHtml(doc.content) + "</div></div>";
            }
            ragResults.innerHTML = html;
        } catch (e) { ragResults.innerHTML = "<p style=\"color:#ef4444\">\u68c0\u7d22\u5931\u8d25: " + e.message + "</p>"; }
    }

    // ====== 工具函数 ======
    function escHtml(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function escAttr(text) {
        return String(text).replace(/"/g, "&quot;").replace(/'/g, "&#39;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // ====== 启动 ======
    init();
})();