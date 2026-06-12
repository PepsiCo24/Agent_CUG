// ============================================================
// Agent_CUG — ChatGPT 风格前端 JS
// ============================================================

(function () {
    "use strict";
    "use strict";


    // ====== Auth State ======
    var authToken = localStorage.getItem("agent_cug_token") || "";
    var currentUser = null;

    // ====== Auth Functions ======
    function showAuth(show) {
        var overlay = document.getElementById("authOverlay");
        if (overlay) overlay.style.display = show ? "flex" : "none";
        if (!show) {
            document.getElementById("loginUsername").value = "";
            document.getElementById("loginPassword").value = "";
            document.getElementById("regUsername").value = "";
            document.getElementById("regPassword").value = "";
            document.getElementById("regPassword2").value = "";
            document.getElementById("authError").style.display = "none";
        }
    }

    function showAuthError(msg) {
        var el = document.getElementById("authError");
        if (el) { el.textContent = msg; el.style.display = "block"; }
    }

    async function apiCall(url, method, body) {
        var headers = { "Content-Type": "application/json" };
        if (authToken) headers["Authorization"] = "Bearer " + authToken;
        var opts = { method: method, headers: headers };
        if (body) opts.body = JSON.stringify(body);
        var resp = await fetch(url, opts);
        var data = await resp.json().catch(function() { return {}; });
        if (!resp.ok) throw new Error(data.detail || "请求失败 " + resp.status);
        return data;
    }

    async function migrateDeviceConversations() {
        if (!authToken || !deviceId) return;
        try {
            var resp = await fetch("/api/auth/migrate", {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
                body: JSON.stringify({ device_id: deviceId }),
            });
            var data = await resp.json();
            if (data.migrated > 0) console.log("Migrated " + data.migrated + " conversations");
        } catch (e) { console.warn("Migration failed:", e); }
    }

    async function doLogin() {
        var username = document.getElementById("loginUsername").value.trim();
        var password = document.getElementById("loginPassword").value;
        if (!username || !password) { showAuthError("请填写用户名和密码"); return; }
        try {
            var data = await apiCall("/api/auth/login", "POST", { username: username, password: password });
            authToken = data.token;
            currentUser = data.user;
            localStorage.setItem("agent_cug_token", authToken);
            localStorage.setItem("agent_cug_user", JSON.stringify(currentUser));
            updateUserUI();
            showAuth(false);
            await migrateDeviceConversations();
            _loadingHistory = false;
            loadHistory();
        } catch (e) { showAuthError(e.message); }
    }

    async function doRegister() {
        var username = document.getElementById("regUsername").value.trim();
        var email = document.getElementById("regEmail").value.trim();
        var password = document.getElementById("regPassword").value;
        var password2 = document.getElementById("regPassword2").value;
        if (!username || !password) { showAuthError("请填写用户名和密码"); return; }
        if (username.length < 3) { showAuthError("用户名至少3个字符"); return; }
        if (password.length < 6) { showAuthError("密码至少6个字符"); return; }
        if (password !== password2) { showAuthError("两次密码不一致"); return; }
        try {
            var data = await apiCall("/api/auth/register", "POST", { username: username, password: password, email: email });
            authToken = data.token;
            currentUser = data.user;
            localStorage.setItem("agent_cug_token", authToken);
            localStorage.setItem("agent_cug_user", JSON.stringify(currentUser));
            updateUserUI();
            showAuth(false);
            await migrateDeviceConversations();
            _loadingHistory = false;
            loadHistory();
        } catch (e) { showAuthError(e.message); }
    }

    function doLogout() {
        authToken = "";
        currentUser = null;
        localStorage.removeItem("agent_cug_token");
        localStorage.removeItem("agent_cug_user");
        // Keep deviceId for anonymous history
        conversationId = null;
        updateUserUI();
        _loadingHistory = false;
        loadHistory();
        // Clear chat
        var el = document.getElementById("chatMessages");
        if (el) el.innerHTML = "";
        var ws = document.getElementById("welcomeScreen");
        if (ws) ws.style.display = "flex";
    }

    function updateUserUI() {
        var display = document.getElementById("userNameDisplay");
        var sidebarName = document.getElementById("sidebarUserName");
        var panelName = document.getElementById("panelUserName");
        var panelEmail = document.getElementById("panelUserEmail");
        var avatar = document.getElementById("userAvatar");
        var panelAvatar = document.querySelector(".user-panel-header .user-avatar");
        var loggedOut = document.getElementById("panelLoggedOut");
        var loggedIn = document.getElementById("panelLoggedIn");

        if (currentUser && currentUser.username) {
            if (display) display.textContent = currentUser.username;
            if (sidebarName) sidebarName.textContent = currentUser.username;
            if (panelName) panelName.textContent = currentUser.username;
            if (panelEmail) panelEmail.textContent = currentUser.email || "";
            if (avatar) avatar.textContent = (currentUser.username || "U").charAt(0).toUpperCase();
            if (panelAvatar) panelAvatar.textContent = (currentUser.username || "U").charAt(0).toUpperCase();
            if (loggedOut) loggedOut.style.display = "none";
            if (loggedIn) loggedIn.style.display = "block";
        } else {
            if (display) display.textContent = "登录";
            if (sidebarName) sidebarName.textContent = "未登录";
            if (panelName) panelName.textContent = "未登录";
            if (panelEmail) panelEmail.textContent = "";
            if (avatar) avatar.textContent = "🤖";
            if (panelAvatar) panelAvatar.textContent = "🤖";
            if (loggedOut) loggedOut.style.display = "block";
            if (loggedIn) loggedIn.style.display = "none";
        }
    }

    function loadSavedUser() {
        try {
            var u = localStorage.getItem("agent_cug_user");
            if (u) currentUser = JSON.parse(u);
            authToken = localStorage.getItem("agent_cug_token") || "";
            if (currentUser && !authToken) { currentUser = null; localStorage.removeItem("agent_cug_user"); }
        } catch (e) { currentUser = null; }
        updateUserUI();
    }

    // ====== Auth Event Handlers ======
    function setupAuthEvents() {
        // ChatGPT 风格用户菜单按钮 — 点击切换面板
        var userMenuBtn = document.getElementById("userMenuBtn");
        var userPanel = document.getElementById("userPanel");
        if (userMenuBtn && userPanel) {
            userMenuBtn.addEventListener("click", function(e) {
                e.stopPropagation();
                var isOpen = userPanel.style.display === "block";
                userPanel.style.display = isOpen ? "none" : "block";
                userMenuBtn.classList.toggle("open", !isOpen);
            });
            // 点击面板外部关闭
            document.addEventListener("click", function(e) {
                if (!userMenuBtn.contains(e.target) && !userPanel.contains(e.target)) {
                    userPanel.style.display = "none";
                    userMenuBtn.classList.remove("open");
                }
            });
        }

        // 面板内按钮
        var panelLoginBtn = document.getElementById("panelLoginBtn");
        if (panelLoginBtn) panelLoginBtn.addEventListener("click", function() {
            userPanel.style.display = "none";
            userMenuBtn.classList.remove("open");
            // 切换到登录 tab
            var tabs = document.querySelectorAll(".auth-tab");
            tabs.forEach(function(x) { x.classList.remove("active"); });
            tabs[0].classList.add("active");
            document.getElementById("loginForm").style.display = "block";
            document.getElementById("registerForm").style.display = "none";
            document.getElementById("authError").style.display = "none";
            showAuth(true);
        });

        var panelRegBtn = document.getElementById("panelRegBtn");
        if (panelRegBtn) panelRegBtn.addEventListener("click", function() {
            userPanel.style.display = "none";
            userMenuBtn.classList.remove("open");
            // 切换到注册 tab
            var tabs = document.querySelectorAll(".auth-tab");
            tabs.forEach(function(x) { x.classList.remove("active"); });
            tabs[1].classList.add("active");
            document.getElementById("loginForm").style.display = "none";
            document.getElementById("registerForm").style.display = "block";
            document.getElementById("authError").style.display = "none";
            showAuth(true);
        });

        var panelLogoutBtn = document.getElementById("panelLogoutBtn");
        if (panelLogoutBtn) panelLogoutBtn.addEventListener("click", function() {
            userPanel.style.display = "none";
            userMenuBtn.classList.remove("open");
            doLogout();
        });

        var panelSettingBtn = document.getElementById("panelSettingBtn");
        if (panelSettingBtn) panelSettingBtn.addEventListener("click", function() {
            userPanel.style.display = "none";
            userMenuBtn.classList.remove("open");
            // 切换到设置面板
            var navItems = document.querySelectorAll(".sidebar-nav-item");
            navItems.forEach(function(x) { x.classList.remove("active"); });
            var settingsNav = document.querySelector('[data-panel="settings"]');
            if (settingsNav) settingsNav.classList.add("active");
            switchPanel("settings");
        });

        // Panel social buttons
        var panelQQ = document.querySelector(".panel-social .social-btn.qq");
        if (panelQQ) panelQQ.addEventListener("click", function() {
            showAuthError("QQ登录功能开发中，请使用账号密码登录");
        });
        var panelWX = document.querySelector(".panel-social .social-btn.wx");
        if (panelWX) panelWX.addEventListener("click", function() {
            showAuthError("微信登录功能开发中，请使用账号密码登录");
        });
        var panelQRBtn = document.getElementById("panelQRBtn");
        if (panelQRBtn) panelQRBtn.addEventListener("click", function() {
            userPanel.style.display = "none";
            userMenuBtn.classList.remove("open");
            showAuthError("扫码登录功能开发中，请使用账号密码登录");
            showAuth(true);
        });


                // Auth modal social buttons
        var authQQ = document.querySelector(".auth-social-btn.qq");
        if (authQQ) authQQ.addEventListener("click", function() {
            showAuthError("QQ登录功能开发中，请使用账号密码登录");
        });
        var authWX = document.querySelector(".auth-social-btn.wx");
        if (authWX) authWX.addEventListener("click", function() {
            showAuthError("微信登录功能开发中，请使用账号密码登录");
        });

// Auth overlay events
        var closeBtn = document.getElementById("authClose");
        if (closeBtn) closeBtn.addEventListener("click", function() { showAuth(false); });

        var overlay = document.getElementById("authOverlay");
        if (overlay) overlay.addEventListener("click", function(e) { if (e.target === overlay) showAuth(false); });

        var loginBtn = document.getElementById("loginBtn");
        if (loginBtn) loginBtn.addEventListener("click", doLogin);

        var regBtn = document.getElementById("regBtn");
        if (regBtn) regBtn.addEventListener("click", doRegister);

        // Tab switching
        var tabs = document.querySelectorAll(".auth-tab");
        tabs.forEach(function(t) {
            t.addEventListener("click", function() {
                tabs.forEach(function(x) { x.classList.remove("active"); });
                t.classList.add("active");
                var isLogin = t.dataset.tab === "login";
                document.getElementById("loginForm").style.display = isLogin ? "block" : "none";
                document.getElementById("registerForm").style.display = isLogin ? "none" : "block";
                document.getElementById("authError").style.display = "none";
            });
        });

        // Enter key to submit
        document.getElementById("loginPassword").addEventListener("keydown", function(e) {
            if (e.key === "Enter") doLogin();
        });
        document.getElementById("regPassword2").addEventListener("keydown", function(e) {
            if (e.key === "Enter") doRegister();
        });
    }

    function fetchWithAuth(url, opts) {
        opts = opts || {};
        opts.headers = opts.headers || {};
        if (authToken) opts.headers["Authorization"] = "Bearer " + authToken;
        if (deviceId) opts.headers["X-Device-Id"] = deviceId;
        return fetch(url, opts);
    }

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
    var docList = document.getElementById("docList");
    var refreshDocListBtn = document.getElementById("refreshDocListBtn");
    var docSelectBtn = document.getElementById("docSelectBtn");
    var docSelectorDropdown = document.getElementById("docSelectorDropdown");
    var docSelectorList = document.getElementById("docSelectorList");
    var docSelectorCount = document.getElementById("docSelectorCount");
    var ragQueryInput = document.getElementById("ragQueryInput");
    var ragQueryBtn = document.getElementById("ragQueryBtn");
    var ragResults = document.getElementById("ragResults");
    var docCountEl = document.getElementById("docCount");
    var docTagsArea = document.getElementById("docTagsArea");
    var docTagsList = document.getElementById("docTagsList");

    // ====== 状态 ======
    var conversationId = null;
    var isStreaming = false;
    var messages = [];
    var conversations = [];
    var _pendingDeletes = {};
    var deviceId = getDeviceId();
    var selectedDocIds = []; // currently selected document IDs for RAG
    var loadedDocs = []; // all loaded documents
    
    // ====== Document Tag Management ======
    function addDocTag(filename) {
        for (var i = 0; i < uploadedFiles.length; i++) {
            if (uploadedFiles[i].name === filename) return;
        }
        uploadedFiles.push({ name: filename, time: Date.now() });
        renderDocTags();
    }

    function removeDocTag(filename) {
        uploadedFiles = uploadedFiles.filter(function(f) { return f.name !== filename; });
        renderDocTags();
    }

    function renderDocTags() {
        if (!docTagsArea || !docTagsList) return;
        if (uploadedFiles.length === 0) {
            docTagsArea.style.display = 'none';
            docTagsList.innerHTML = '';
            return;
        }
        docTagsArea.style.display = 'flex';
        var h = '';
        for (var i = 0; i < uploadedFiles.length; i++) {
            var f = uploadedFiles[i];
            h += '<div class="doc-tag">' +
                '<span class="tag-name" title="' + escAttr(f.name) + '">' + escHtml(f.name) + '</span>' +
                '<span class="tag-remove" data-file="' + escAttr(f.name) + '">&times;</span>' +
                '</div>';
        }
        docTagsList.innerHTML = h;
        // Attach click handlers
        var removes = docTagsList.querySelectorAll('.tag-remove');
        for (var j = 0; j < removes.length; j++) {
            removes[j].onclick = function() {
                removeDocTag(this.getAttribute('data-file'));
                refreshDocCount();
            };
        }
    }
var uploadedFiles = [];  // Track uploaded documents

    function getDeviceId() {
        var id = localStorage.getItem("agent_cug_did");
        if (!id) {
            id = "did-" + Date.now().toString(36) + "-" + Math.random().toString(36).substring(2, 10);
            localStorage.setItem("agent_cug_did", id);
        }
        return id;
    }

    
    // ====== 暗色模式检测 ======
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
    if (prefersDark.matches) document.body.classList.add("dark-mode");
    prefersDark.addEventListener("change", function(e) {
        document.body.classList.toggle("dark-mode", e.matches);
    });

    // ====== 初始化 ======
    // Theme toggle
    var themeToggleBtn = null;
    function getTheme() {
        var s = localStorage.getItem("agent_cug_theme");
        if (s === "light" || s === "dark") return s;
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    function setTheme(t) {
        document.documentElement.setAttribute("data-theme", t);
        localStorage.setItem("agent_cug_theme", t);
    }
    function toggleTheme() {
        var c = getTheme();
        setTheme(c === "dark" ? "light" : "dark");
    }
    setTheme(getTheme());

    function init() {
        loadSavedUser();
        setupAuthEvents();
        loadConfig();
        loadHistory();
        setupEventListeners();
        autoResizeInput();
    }

    async function loadConfig() {
        try {
            var resp = await fetchWithAuth("/api/config");
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

    var _loadingHistory = false;
    async function loadHistory() {
        if (_loadingHistory) return;
        _loadingHistory = true;
        try {
            var resp = await fetchWithAuth("/api/history?device_id=" + encodeURIComponent(deviceId));
            var data = await resp.json();
            conversations = data.conversations || [];
            conversations = conversations.filter(function(c) { return !_pendingDeletes[c.id]; });
            renderHistory();
        } catch (e) { console.warn("\u5386\u53f2\u52a0\u8f7d\u5931\u8d25:", e); }
        _loadingHistory = false;
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
                "<span class=\"history-title\">" + escHtml(stripMarkdown(conv.title)) + "</span>" +
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
        themeToggleBtn = document.getElementById("themeToggleBtn");
        if (themeToggleBtn) themeToggleBtn.addEventListener("click", toggleTheme);
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
        refreshDocListBtn.addEventListener("click", function() { loadDocList(); });
        docSelectBtn.addEventListener("click", function(e) { 
            e.stopPropagation();
            toggleDocSelector();
        });
        // Close doc selector on outside click
        document.addEventListener("click", function(e) {
            if (docSelectorDropdown && docSelectorDropdown.style.display !== "none") {
                if (!docSelectorDropdown.contains(e.target) && e.target !== docSelectBtn) {
                    docSelectorDropdown.style.display = "none";
                }
            }
        });
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
    "use strict";
                    btn.textContent = "\u2713 \u5df2\u590d\u5236";
                    btn.classList.add("copied");
                    setTimeout(function () {
    "use strict"; btn.textContent = "\u590d\u5236"; btn.classList.remove("copied"); }, 2000);
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
        else if (panel === "rag") { ragPanel.classList.add("active"); refreshDocCount(); loadDocList(); }
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
            var resp = await fetch("/api/history/" + convId, {
                headers: authToken ? { "Authorization": "Bearer " + authToken } : {}
            });
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
    // ====== 自定义弹窗 ======
    function showModal(title, message, showInput, callback) {
        var modal = document.createElement("div");
        modal.className = "custom-modal-overlay";
        var inputHtml = showInput ? '<input type="text" class="custom-modal-input" id="modalInput" placeholder="' + escHtml(message) + '">' : '<p class="custom-modal-message">' + escHtml(message) + '</p>';
        var btnHtml = showInput
            ? '<button class="custom-modal-btn primary" id="modalOk">确定</button><button class="custom-modal-btn" id="modalCancel">取消</button>'
            : '<button class="custom-modal-btn danger" id="modalOk">删除</button><button class="custom-modal-btn" id="modalCancel">取消</button>';
        modal.innerHTML = '<div class="custom-modal"><div class="custom-modal-header">' + escHtml(title) + '</div><div class="custom-modal-body">' + inputHtml + '</div><div class="custom-modal-footer">' + btnHtml + '</div></div>';
        document.body.appendChild(modal);
        var input = document.getElementById("modalInput");
        if (input) { input.focus(); input.select(); }
        document.getElementById("modalOk").addEventListener("click", function () {
            modal.remove();
            if (callback) callback(showInput ? (input ? input.value.trim() : "") : true);
        });
        document.getElementById("modalCancel").addEventListener("click", function () {
            modal.remove();
            if (callback) callback(null);
        });
        modal.addEventListener("click", function (e) { if (e.target === modal) { modal.remove(); if (callback) callback(null); } });
        // Keyboard support
        document.addEventListener("keydown", function handler(e) {
            if (e.key === "Escape") { modal.remove(); document.removeEventListener("keydown", handler); if (callback) callback(null); }
            if (e.key === "Enter" && input) { modal.remove(); document.removeEventListener("keydown", handler); if (callback) callback(input.value.trim()); }
        });
    }

    function deleteConversation(convId) {
        if (!convId) return;
        showModal("删除对话", "确定要删除这个对话吗？此操作不可撤销。", false, function (confirmed) {
            if (!confirmed) return;
            _pendingDeletes[convId] = true;
            // Optimistic: remove from DOM immediately
            conversations = conversations.filter(function(c) { return c.id !== convId; });
            if (conversationId === convId) {
                conversationId = null;
                messages = [];
                var rows = chatMessages.querySelectorAll(".message-row");
                for (var ri = 0; ri < rows.length; ri++) rows[ri].remove();
                if (welcomeScreen) { welcomeScreen.style.display = "flex"; }
                messageInput.value = "";
                messageInput.focus();
            }
            renderHistory();
            // Confirm delete with server (rollback on failure)
            fetch("/api/history/" + convId, {
                method: "DELETE",
                headers: authToken ? { "Authorization": "Bearer " + authToken } : {}
            }).then(function (resp) {
                delete _pendingDeletes[convId];
                if (!resp.ok) loadHistory();
            }).catch(function (e) {
                console.warn("删除失败:", e);
                delete _pendingDeletes[convId];
                loadHistory();
            });
        });
    }

    // ====== 重命名对话 ======
    function renameConversation(convId) {
        if (!convId) return;
        showModal("重命名对话", "请输入新标题", true, function (newTitle) {
            if (!newTitle) return;
            var _h = { "Content-Type": "application/json" };
            if (authToken) _h["Authorization"] = "Bearer " + authToken;
            fetch("/api/history/" + convId + "/title", {
                method: "PUT",
                headers: _h,
                body: JSON.stringify({ title: newTitle }),
            }).then(function (resp) {
                if (resp.ok) loadHistory();
            }).catch(function (e) { console.warn("重命名失败:", e); });
        });
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
            var headers = { "Content-Type": "application/json" };
            if (authToken) headers["Authorization"] = "Bearer " + authToken;
            var chatBody = { message: text, conversation_id: conversationId, device_id: deviceId };
            if (selectedDocIds.length > 0) chatBody.doc_ids = selectedDocIds;
            var response = await fetch("/api/chat/stream", {
                method: "POST",
                headers: headers,
                body: JSON.stringify(chatBody),
            });
            if (!response.ok) {
                var errData = await response.json().catch(function () {
    "use strict"; return {}; });
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
                // ??????????? tokenizer ???
                fullText = cleanText(fullText);
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
        var contentDiv = document.createElement("div");
        contentDiv.className = "message-content";
        if (streaming) contentDiv.classList.add("streaming-cursor");
        if (content) contentDiv.innerHTML = renderMarkdown(content);
        inner.appendChild(contentDiv);
        // Edit button for user messages
        if (role === "user") {
            var userActionsDiv = document.createElement("div");
            userActionsDiv.className = "message-actions";
            var editBtn = document.createElement("button");
            editBtn.className = "message-edit-btn";
            editBtn.title = "编辑消息";
            editBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>';
            editBtn.addEventListener("click", function () {
                editUserMessage(row);
            });
            userActionsDiv.appendChild(editBtn);
            contentDiv.appendChild(userActionsDiv);
        }
        // Copy button for assistant/tool messages
        if (role === "assistant" || role === "tool") {
            var actionsDiv = document.createElement("div");
            actionsDiv.className = "message-actions";
            var copyBtn = document.createElement("button");
            copyBtn.className = "message-copy-btn";
            copyBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg><span>复制</span>';
            copyBtn.addEventListener("click", function () {
                var txt = contentDiv.textContent || "";
                copyToClipboard(txt).then(function () {
    "use strict";
                    copyBtn.classList.add("copied");
                    copyBtn.querySelector("span").textContent = "✓ 已复制";
                    setTimeout(function () {
    "use strict";
                        copyBtn.classList.remove("copied");
                        copyBtn.querySelector("span").textContent = "复制";
                    }, 2000);
                });
            });
            actionsDiv.appendChild(copyBtn);
            inner.appendChild(actionsDiv);
        }

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
                html += "<div class=\"tool-call-display\">"
                    "<div class=\"tool-result\">" + escHtml(String(toolCalls[i].result || "")) + "</div></div>";
            }
        }
        text = cleanText(text);
        html += renderContentWithThinking(text);
        el.innerHTML = html;
        el.classList.add("streaming-cursor");
    }

    function renderFinal(text, toolCalls) {
        var html = "";
        if (toolCalls && toolCalls.length > 0) {
            for (var i = 0; i < toolCalls.length; i++) {
                html += "<div class=\"tool-call-display\">"
                    "<div class=\"tool-result\">" + escHtml(String(toolCalls[i].result || "")) + "</div></div>";
            }
        }
        html += renderContentWithThinking(text);
        return html;
    }


    function cleanText(text) {
        if (!text) return text;
        // Preserve intentional paragraph breaks (double newlines)
        text = text.replace(/\r?\n\r?\n/g, "%%PARA%%");
        // Collapse all remaining single newlines to spaces
        text = text.replace(/[\r\n]+/g, " ");
        // Restore paragraph breaks
        text = text.replace(/%%PARA%%/g, "\n\n");
        // Remove spaces between consecutive digits (e.g. "2 0 2 6" -> "2026")
        text = text.replace(/(\d) (\d)/g, "$1$2");
        // Add space between CJK and alphanumeric
        text = text.replace(/([\u2e80-\u9fff\u3000-\u303f\uff00-\uffef\u3200-\u33ff\uf900-\ufaff])([a-zA-Z0-9])/g, "$1 $2");
        text = text.replace(/([a-zA-Z0-9])([\u2e80-\u9fff\u3000-\u303f\uff00-\uffef\u3200-\u33ff\uf900-\ufaff])/g, "$1 $2");
        // Collapse multiple spaces
        text = text.replace(/  +/g, " ");
        return text;
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
        // ====== Markdown ?? ======
    function renderMarkdown(text) {
        if (!text) return "";

        // 1. Extract and protect code blocks first
        var codeBlocks = [];
        var html = text.replace(/```(\w*)\r?\n([\s\S]*?)```/g, function (match, lang, code) {
            codeBlocks.push({ lang: lang || "code", code: code.trim() });
            return "%%CODEBLOCK_" + (codeBlocks.length - 1) + "%%";
        });

        // 2. Escape HTML
        html = escHtml(html);

        // 3. Restore code blocks
        html = html.replace(/%%CODEBLOCK_(\d+)%%/g, function (match, idx) {
            var block = codeBlocks[parseInt(idx)];
            var escapedCode = escHtml(block.code);
            var attrCode = escAttr(block.code).replace(/\n/g, '&#10;');
            return '<div class="code-block-header"><span>' + escHtml(block.lang) +
                '</span><button class="copy-btn" data-code="' + attrCode + '">\u590d\u5236</button></div>' +
                '<pre><code>' + escapedCode + '</code></pre>';
        });

        // 4. Inline code
        html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');

        // 5. Headers
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

        // 6. Bold+Italic (***), Bold (**), Italic (*) - allow newlines inside
        html = html.replace(/\*\*\*([^*]+)\*\*\*/g, '<strong><em>$1</em></strong>');
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)/g, '<em>$1</em>');

        // 7. Strikethrough
        html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>');

        // 8. Links and images
        html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%">');
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

        // 9. Horizontal rule
        html = html.replace(/^(\*{3,}|-{3,}|_{3,})$/gm, '<hr>');

        // 10. Ordered lists - use placeholder to isolate from unordered list regex
        html = html.replace(/((?:^\d+\. .+$\n?)+)/gm, function(match) {
            var items = match.replace(/^\d+\. (.+)$/gm, '<_LI_>$1</_LI_>');
            return '<_OL_>' + items.trim() + '</_OL_>';
        });

        // 11. Unordered lists
        html = html.replace(/^[\*\-] (.+)$/gm, '<li>$1</li>');
        html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

        // Restore ordered list tags
        html = html.replace(/<_OL_>/g, '<ol>');
        html = html.replace(/<\/_OL_>/g, '</ol>');
        html = html.replace(/<_LI_>/g, '<li>');
        html = html.replace(/<\/_LI_>/g, '</li>');

        // 12. Blockquote
        html = html.replace(/^&gt;\s?(.+)$/gm, '<blockquote>$1</blockquote>');

        // 13. Table (skip separator row, use <th> for header)
        var lines = html.split("\n");
        var newLines = [];
        var tableRows = [];
        var isHeaderRow = true;

        for (var li = 0; li < lines.length; li++) {
            var line = lines[li];
            if (/^\|.+\|$/.test(line)) {
                var cells = line.split("|").filter(function(c) { return c.trim() !== ""; });
                if (cells.length < 2) { newLines.push(line); continue; }

                var isSep = true;
                for (var ci = 0; ci < cells.length; ci++) {
                    if (!/^[-: ]+$/.test(cells[ci].trim())) { isSep = false; break; }
                }
                if (isSep) { isHeaderRow = false; continue; }

                var rowHtml = "<tr>";
                var tag = isHeaderRow ? "th" : "td";
                for (var ci2 = 0; ci2 < cells.length; ci2++) {
                    rowHtml += "<" + tag + ">" + cells[ci2].trim() + "</" + tag + ">";
                }
                rowHtml += "</tr>";
                tableRows.push(rowHtml);
                isHeaderRow = false;
            } else {
                if (tableRows.length > 0) {
                    newLines.push("<table>" + tableRows.join("\n") + "</table>");
                    tableRows = [];
                    isHeaderRow = true;
                }
                newLines.push(line);
            }
        }
        if (tableRows.length > 0) {
            newLines.push("<table>" + tableRows.join("\n") + "</table>");
        }
        html = newLines.join("\n");

        // 14. Paragraph wrapping - protect HTML blocks first
        var protectedBlocks = [];
        html = html.replace(/(<(?:pre|table|ul|ol|blockquote)[\s\S]*?<\/(?:pre|table|ul|ol|blockquote)>)/g, function(m) {
            protectedBlocks.push(m);
            return "%%PROTECT_" + (protectedBlocks.length - 1) + "%%";
        });

        var paragraphs = html.split(/\r?\n\r?\n/);
        html = "";
        for (var p = 0; p < paragraphs.length; p++) {
            var para = paragraphs[p].trim();
            if (!para) continue;
            if (para.indexOf("<h") === 0 || para.indexOf("<pre") === 0 || para.indexOf("<div") === 0 ||
                para.indexOf("<ul") === 0 || para.indexOf("<ol") === 0 || para.indexOf("<blockquote") === 0 ||
                para.indexOf("<hr") === 0 || para.indexOf("<table") === 0 ||
                para.indexOf("<li") === 0 ||
                para.indexOf("%%PROTECT_") === 0) {
                html += para + "\n";
            } else {
                html += "<p>" + para.replace(/[\r\n]+/g, " ") + "</p>\n";
            }
        }

        // Restore protected blocks
        html = html.replace(/%%PROTECT_(\d+)%%/g, function(m, idx) {
            return protectedBlocks[parseInt(idx)] || "";
        });

        // 15. Clean up unmatched double-asterisk markers
        html = html.replace(/\*\*/g, '');
        html = html.replace(/~~/g, '');

        return html;
    }

    
    // ====== ?????? (????) ======
    function editUserMessage(row) {
        var contentEl = row.querySelector(".message-content");
        var actionsEl = row.querySelector(".message-actions");
        var originalText = contentEl ? (contentEl.textContent || "").trim() : "";
        if (!originalText || !contentEl) return;

        // Already editing?
        if (contentEl.querySelector(".message-edit-textarea")) return;

        // Get text without the edit button text
        var clone = contentEl.cloneNode(true);
        var a = clone.querySelector(".message-actions");
        if (a) a.remove();
        var textOnly = (clone.textContent || "").trim();
        var originalHTML = contentEl.innerHTML;

        // Replace content with textarea
        contentEl.innerHTML = "";
        var textarea = document.createElement("textarea");
        textarea.className = "message-edit-textarea";
        textarea.value = textOnly;
        contentEl.appendChild(textarea);

        // Add confirm/cancel buttons
        var btnRow = document.createElement("div");
        btnRow.className = "message-edit-actions";

        var cancelBtn = document.createElement("button");
        cancelBtn.className = "message-edit-cancel";
        cancelBtn.textContent = "\u53d6\u6d88";
        cancelBtn.addEventListener("click", function () {
            contentEl.innerHTML = originalHTML;
            rebindEditButton(row);
        });

        var confirmBtn = document.createElement("button");
        confirmBtn.className = "message-edit-confirm";
        var svgSpan = document.createElement("span");
        svgSpan.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:4px"><line x1="22" y1="2" x2="11" y2="13"></line><polyline points="11 13 7 9 4 9 11 22 22 2"></polyline></svg>';
        confirmBtn.appendChild(svgSpan);
        confirmBtn.appendChild(document.createTextNode("\u53d1\u9001"));
        confirmBtn.addEventListener("click", function () {
            submitEdit(row, contentEl, textarea, textOnly);
        });

        btnRow.appendChild(cancelBtn);
        btnRow.appendChild(confirmBtn);
        contentEl.appendChild(btnRow);

        textarea.focus();
        textarea.select();

        textarea.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submitEdit(row, contentEl, textarea, textOnly);
            } else if (e.key === "Escape") {
                e.preventDefault();
                contentEl.innerHTML = originalHTML;
                rebindEditButton(row);
            }
        });

        textarea.addEventListener("input", function () {
            textarea.style.height = "auto";
            textarea.style.height = textarea.scrollHeight + "px";
        });
        textarea.style.height = textarea.scrollHeight + "px";
    }

    function rebindEditButton(row) {
        var editBtn = row.querySelector(".message-edit-btn");
        if (editBtn) {
            var newBtn = editBtn.cloneNode(true);
            editBtn.parentNode.replaceChild(newBtn, editBtn);
            newBtn.addEventListener("click", function () {
                editUserMessage(row);
            });
        }
    }

    function submitEdit(row, contentEl, textarea, originalText) {
        var newText = textarea.value.trim();
        if (!newText) return;

        var rows = chatMessages.children;
        var rowIdx = -1;
        for (var i = 0; i < rows.length; i++) {
            if (rows[i] === row) { rowIdx = i; break; }
        }
        if (rowIdx === -1) return;

        var userMsgCount = 0;
        for (var i = 0; i <= rowIdx; i++) {
            if (rows[i].classList.contains("user")) userMsgCount++;
        }

        var found = 0;
        for (var i = 0; i < messages.length; i++) {
            if (messages[i].role === "user") {
                found++;
                if (found === userMsgCount) {
                    messages[i].content = newText;
                    if (i + 1 < messages.length && messages[i + 1].role === "assistant") {
                        messages.splice(i + 1, 1);
                    }
                    break;
                }
            }
        }

        var next = row.nextElementSibling;
        while (next && !next.classList.contains("user")) {
            var toRemove = next;
            next = next.nextElementSibling;
            toRemove.remove();
        }

        contentEl.innerHTML = "<p>" + escHtml(newText) + "</p>";
        var actionsDiv = document.createElement("div");
        actionsDiv.className = "message-actions";
        var editBtn = document.createElement("button");
        editBtn.className = "message-edit-btn";
        editBtn.title = "\u7f16\u8f91\u6d88\u606f";
        editBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>';
        editBtn.addEventListener("click", function () {
            editUserMessage(row);
        });
        actionsDiv.appendChild(editBtn);
        contentEl.appendChild(actionsDiv);

        sendEditedMessage(newText);
    }

    function sendEditedMessage(text) {
        if (!text || isStreaming) return;
        isStreaming = true;
        sendBtn.disabled = true;
        if (welcomeScreen) welcomeScreen.style.display = "none";

        var alreadyInMessages = false;
        for (var i = messages.length - 1; i >= 0; i--) {
            if (messages[i].role === "user" && messages[i].content === text) {
                alreadyInMessages = true;
                break;
            }
        }
        if (!alreadyInMessages) {
            messages.push({ role: "user", content: text });
        }

        var assistantRow = addMessage("assistant", "", true);
        var contentEl2 = assistantRow.querySelector(".message-content");
        var fullText = "";
        var toolCalls = [];

        var _headers = { "Content-Type": "application/json" };
            if (authToken) _headers["Authorization"] = "Bearer " + authToken;
            var chatBody2 = { message: text, conversation_id: conversationId, device_id: deviceId };
            if (selectedDocIds.length > 0) chatBody2.doc_ids = selectedDocIds;
            fetch("/api/chat/stream", {
            method: "POST",
            headers: _headers,
            body: JSON.stringify(chatBody2),
        }).then(function (response) {
            if (!response.ok) {
                return response.json().catch(function () {
    "use strict"; return {}; }).then(function (errData) {
                    throw new Error(errData.detail || "????: " + response.status);
                });
            }
            return response.body.getReader();
        }).then(function (reader) {
            var decoder = new TextDecoder();
            var buffer = "";

            function pump() {
                return reader.read().then(function (chunk) {
                    if (chunk.done) {
                        if (contentEl2) {
                            contentEl2.classList.remove("streaming-cursor");
                            fullText = fullText.replace(/(\d) (\d)/g, "$1$2");
                            contentEl2.innerHTML = renderFinal(fullText, toolCalls);
                        }
                        messages.push({ role: "assistant", content: fullText });
                        loadHistory();
                        isStreaming = false;
                        sendBtn.disabled = false;
                        messageInput.focus();
                        return;
                    }
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
                            processStreamEvent2(currentEvent, currentData);
                            currentEvent = null;
                        }
                    }
                    if (currentEvent) processStreamEvent2(currentEvent, currentData);
                    if (contentEl2) renderStreamingContent(contentEl2, fullText, toolCalls);
                    scrollToBottom();
                    return pump();
                });
            }

            function processStreamEvent2(event, data) {
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
                    if (contentEl2) contentEl2.innerHTML = "<p style=\"color:#ef4444\">\u9519\u8bef: " + escHtml(data) + "</p>";
                }
            }

            return pump();
        }).catch(function (error) {
            if (contentEl2) {
                contentEl2.classList.remove("streaming-cursor");
                contentEl2.innerHTML = "<p style=\"color:#ef4444\">\u7f51\u7edc\u9519\u8bef: " + escHtml(error.message) + "</p>";
            }
            isStreaming = false;
            sendBtn.disabled = false;
        });
    }


function scrollToBottom() {
        requestAnimationFrame(function () {
    "use strict";
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
        fileInput.value = ""; refreshDocCount(); renderDocTags(); loadDocList();
    }

    async function handleRagFiles(files) {
        if (!files.length) return;
        for (var i = 0; i < files.length; i++) {
            showUploadStatus("info", "\u23f3 \u6b63\u5728\u5904\u7406 " + files[i].name + "...");
            await uploadFile(files[i]);
        }
        ragFileInput.value = ""; refreshDocCount(); loadDocList();
    }

    async function uploadFile(file) {
        try {
            var formData = new FormData();
            formData.append("file", file);
            var headers = {};
            if (authToken) headers["Authorization"] = "Bearer " + authToken;
            if (deviceId) headers["X-Device-Id"] = deviceId;
            var resp = await fetch("/api/rag/upload", { method: "POST", headers: headers, body: formData });
            var result = await resp.json();
            if (resp.ok) addDocTag(file.name);
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
            var body = { query: query, top_k: 20 };
            if (selectedDocIds.length > 0) body.doc_ids = selectedDocIds;
            var headers = { "Content-Type": "application/json" };
            if (authToken) headers["Authorization"] = "Bearer " + authToken;
            var resp = await fetch("/api/rag/query", {
                method: "POST", headers: headers,
                body: JSON.stringify(body),
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

    function stripMarkdown(text) {
        if (!text) return "";
        text = String(text);
        // Remove images (including truncated)
        text = text.replace(/!\[([^\]]*)\]\([^)]*\)?/g, "$1");
        // Remove links, keep text (handle truncated: missing closing paren)
        text = text.replace(/\[([^\]]*)\]\([^)]*\)?/g, "$1");
        // Remove bold markers (handle truncated)
        text = text.replace(/\*\*([^*]*)\*?\*?/g, "$1");
        text = text.replace(/__([^_]*)_?_?/g, "$1");
        // Remove italic markers (handle truncated)
        text = text.replace(/(?<!\*)\*([^*]*)\*?(?!\*)/g, "$1");
        text = text.replace(/(?<!_)_([^_]*)_?(?!_)/g, "$1");
        // Remove headers
        text = text.replace(/^#{1,6}\s+/gm, "");
        // Remove blockquotes
        text = text.replace(/^>\s+/gm, "");
        // Remove code markers
        text = text.replace(/`([^`]*)`?/g, "$1");
        // Remove strikethrough
        text = text.replace(/~~([^~]*)~?~?/g, "$1");
        // Remove horizontal rules
        text = text.replace(/^[-*_]{3,}\s*$/gm, "");
        // Remove list markers
        text = text.replace(/^[\s]*[-*+]\s+/gm, "");
        text = text.replace(/^[\s]*\d+\.\s+/gm, "");
        // Collapse whitespace
        text = text.replace(/\s+/g, " ").trim();
        return text;
    }

    function escHtml(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function escAttr(text) {
        return String(text).replace(/"/g, "&quot;").replace(/'/g, "&#39;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // ====== 启动 ======
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();