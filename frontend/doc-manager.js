// ====== 文档列表管理 ======
var _loadingDocs = false;
async function loadDocList() {
    if (_loadingDocs) return;
    _loadingDocs = true;
    try {
        var resp = await fetchWithAuth("/api/rag/documents");
        var data = await resp.json();
        loadedDocs = data.documents || [];
        renderDocList();
        renderDocSelector();
    } catch (e) { console.warn("加载文档列表失败:", e); }
    _loadingDocs = false;
}

function renderDocList() {
    if (!docList) return;
    if (loadedDocs.length === 0) {
        docList.innerHTML = '<div class="doc-list-empty">暂无文档，上传文件即可开始</div>';
        return;
    }
    var html = "";
    for (var i = 0; i < loadedDocs.length; i++) {
        var d = loadedDocs[i];
        var icon = getDocIcon(d.filename);
        var type = (d.file_type || "").toUpperCase();
        html += '<div class="doc-list-item" data-id="' + d.id + '">' +
            '<div class="doc-list-icon">' + icon + '</div>' +
            '<div class="doc-list-info">' +
                '<div class="doc-list-name" title="' + escHtml(d.filename) + '">' + escHtml(d.filename) + '</div>' +
                '<div class="doc-list-meta">' +
                    '<span>' + type + '</span>' +
                    '<span>' + (d.chunks || 0) + ' 个分块</span>' +
                    '<span>' + formatTime(d.created_at) + '</span>' +
                '</div>' +
            '</div>' +
            '<div class="doc-list-actions">' +
                '<button class="doc-list-action-btn danger" data-action="delete" title="删除">' +
                    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
                        '<polyline points="3 6 5 6 21 6"></polyline>' +
                        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>' +
                    '</svg></button>' +
            '</div></div>';
    }
    docList.innerHTML = html;

    var items = docList.querySelectorAll(".doc-list-action-btn");
    for (var j = 0; j < items.length; j++) {
        items[j].addEventListener("click", function(e) {
            e.stopPropagation();
            var item = this.closest(".doc-list-item");
            var docId = item.dataset.id;
            var action = this.dataset.action;
            if (action === "delete") deleteDocument(docId, item);
        });
    }
}

function getDocIcon(filename) {
    var ext = (filename || "").split(".").pop().toLowerCase();
    if (ext === "pdf") return "\u{1F4D5}";
    if (ext === "docx") return "\u{1F4D8}";
    if (ext === "md" || ext === "markdown") return "\u{1F4DD}";
    if (ext === "txt") return "\u{1F4C4}";
    return "\u{1F4CE}";
}

async function deleteDocument(docId, itemEl) {
    if (!confirm("确定要删除这个文档吗？此操作不可撤销。")) return;
    try {
        var resp = await fetchWithAuth("/api/rag/documents/" + docId, { method: "DELETE" });
        if (!resp.ok) throw new Error("删除失败");
        if (itemEl) itemEl.remove();
        selectedDocIds = selectedDocIds.filter(function(id) { return id !== docId; });
        loadedDocs = loadedDocs.filter(function(d) { return d.id !== docId; });
        renderDocTags();
        renderDocSelector();
        refreshDocCount();
        if (loadedDocs.length === 0) renderDocList();
    } catch (e) { alert("删除失败: " + e.message); }
}



// ====== 文档选择器 ======
function toggleDocSelector() {
    if (!docSelectorDropdown) return;
    if (docSelectorDropdown.style.display === "none") {
        loadDocList().then(function() {
            docSelectorDropdown.style.display = "block";
            renderDocSelector();
        });
    } else {
        docSelectorDropdown.style.display = "none";
    }
}

function renderDocSelector() {
    if (!docSelectorList || !docSelectorCount) return;
    if (loadedDocs.length === 0) {
        docSelectorList.innerHTML = '<div class="doc-selector-empty">暂无文档，请先在知识库中上传</div>';
        docSelectorCount.textContent = "已选 0 个";
        return;
    }
    docSelectorCount.textContent = "已选 " + selectedDocIds.length + " 个";
    var html = "";
    for (var i = 0; i < loadedDocs.length; i++) {
        var d = loadedDocs[i];
        var checked = selectedDocIds.indexOf(d.id) >= 0;
        var cls = checked ? " doc-selector-item-checked" : "";
        html += '<div class="doc-selector-item' + cls + '" data-id="' + d.id + '">' +
            '<input type="checkbox" ' + (checked ? "checked" : "") + ' tabindex="-1">' +
            '<span class="doc-selector-item-name">' + escHtml(d.filename) + '</span>' +
            '<span class="doc-selector-item-chunks">' + (d.chunks || 0) + '块</span>' +
            '</div>';
    }
    html += '<div class="doc-selector-actions">' +
        '<button class="select-all-docs">全选</button>' +
        '<button class="deselect-all-docs">清空</button>' +
        '<button class="primary apply-doc-select">确定</button>' +
        '</div>';
    docSelectorList.innerHTML = html;

    var items = docSelectorList.querySelectorAll(".doc-selector-item");
    for (var j = 0; j < items.length; j++) {
        items[j].addEventListener("click", function(e) {
            var cb = this.querySelector('input[type="checkbox"]');
            cb.checked = !cb.checked;
            if (cb.checked) this.classList.add("doc-selector-item-checked");
            else this.classList.remove("doc-selector-item-checked");
            updateDocSelection();
        });
    }

    var selectAll = docSelectorList.querySelector(".select-all-docs");
    var deselectAll = docSelectorList.querySelector(".deselect-all-docs");
    var applyBtn = docSelectorList.querySelector(".apply-doc-select");
    if (selectAll) selectAll.addEventListener("click", function(e) {
        e.stopPropagation();
        selectedDocIds = loadedDocs.map(function(d) { return d.id; });
        renderDocSelector(); renderDocTags();
    });
    if (deselectAll) deselectAll.addEventListener("click", function(e) {
        e.stopPropagation();
        selectedDocIds = [];
        renderDocSelector(); renderDocTags();
    });
    if (applyBtn) applyBtn.addEventListener("click", function(e) {
        e.stopPropagation();
        updateDocSelection();
        docSelectorDropdown.style.display = "none";
        renderDocTags();
    });
}

function updateDocSelection() {
    if (!docSelectorList) return;
    var cbs = docSelectorList.querySelectorAll('input[type="checkbox"]');
    selectedDocIds = [];
    for (var i = 0; i < cbs.length; i++) {
        if (cbs[i].checked) {
            var item = cbs[i].closest(".doc-selector-item");
            if (item) selectedDocIds.push(item.dataset.id);
        }
    }
    if (docSelectorCount) docSelectorCount.textContent = "已选 " + selectedDocIds.length + " 个";
    updateDocSelectBtn();
}

function updateDocSelectBtn() {
    if (docSelectBtn) {
        if (selectedDocIds.length > 0) {
            docSelectBtn.classList.add("has-selection");
            docSelectBtn.title = "已选 " + selectedDocIds.length + " 个文档";
        } else {
            docSelectBtn.classList.remove("has-selection");
            docSelectBtn.title = "选择知识库文档";
        }
    }
}

