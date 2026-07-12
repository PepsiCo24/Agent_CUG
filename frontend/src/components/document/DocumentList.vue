<template>
  <div class="rounded-gpt border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-3">
    <div class="flex items-center justify-between mb-2">
      <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
        <FolderOpen :size="14" />
        Documents
        <span v-if="documents.length > 0" class="text-xs text-gray-400 font-normal">({{ documents.length }})</span>
      </h4>
      <div class="flex items-center gap-2">
        <button @click="fetchDocs()" class="text-xs text-gpt-accent hover:underline">Refresh</button>
        <button @click="triggerUpload" class="text-xs btn-primary py-1 px-2 flex items-center gap-1">
          <Upload :size="12" /> Upload
        </button>
        <input ref="fileInput" type="file" class="hidden" :accept="acceptFormats" @change="handleUpload" multiple />
      </div>
    </div>

    <!-- Drop zone -->
    <div
      class="text-center py-3 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer hover:border-gpt-accent transition-colors mb-2"
      @click="triggerUpload"
      @dragover.prevent="dragover = true"
      @dragleave.prevent="dragover = false"
      @drop.prevent="handleDrop"
      :class="{ 'border-gpt-accent bg-gpt-accent/5': dragover }"
    >
      <Upload :size="20" class="mx-auto text-gray-400 dark:text-gray-500 mb-1" />
      <p class="text-xs text-gray-500 dark:text-gray-400">Drop files or click to upload</p>
      <p class="text-[10px] text-gray-400 mt-0.5">{{ acceptFormats }}</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-4 text-xs text-gray-400">Loading...</div>

    <!-- Empty -->
    <div v-if="!loading && documents.length === 0" class="text-center py-2 text-xs text-gray-400">
      No documents uploaded yet
    </div>

    <!-- Document list -->
    <div v-if="!loading && documents.length > 0" class="space-y-1 max-h-48 overflow-y-auto">
      <div
        v-for="doc in documents"
        :key="doc.id"
        class="flex items-center gap-2 p-2 rounded-lg hover:bg-white dark:hover:bg-gray-700 transition-colors"
      >
        <FileText :size="14" class="text-gray-400 flex-shrink-0" />
        <span class="text-xs text-gray-600 dark:text-gray-300 truncate flex-1" :title="doc.originalName">{{ doc.originalName }}</span>
        <span class="text-[10px] text-gray-400 flex-shrink-0">{{ formatSize(doc.fileSize) }}</span>
        <span
          class="text-xs px-1.5 py-0.5 rounded font-medium flex-shrink-0"
          :class="statusClass(doc.embeddingStatus)"
        >
          {{ doc.embeddingStatus }}
        </span>
        <button @click="deleteDoc(doc.id)" class="p-0.5 text-gray-400 hover:text-red-500 transition-colors flex-shrink-0">
          <Trash2 :size="12" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import { documentApi } from "@/api/document";
import type { Document } from "@/types";
import { FileText, FolderOpen, Trash2, Upload } from "lucide-vue-next";

const props = defineProps<{ kbId: number; refreshKey?: number }>();
const emit = defineEmits<{ (e: 'uploaded'): void }>();

const documents = ref<Document[]>([]);
const loading = ref(false);
const dragover = ref(false);
const fileInput = ref<HTMLInputElement>();
const acceptFormats = ".pdf,.doc,.docx,.md,.markdown,.txt,.png,.jpg,.jpeg,.gif";

let pollTimer: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  fetchDocs();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});

watch(() => props.kbId, () => fetchDocs());
watch(() => props.refreshKey, () => fetchDocs());

function startPolling() {
  stopPolling();
  pollTimer = setInterval(() => {
    const needsPoll = documents.value.some(
      d => d.embeddingStatus === 'PENDING' || d.embeddingStatus === 'PROCESSING'
    );
    if (needsPoll) {
      fetchDocs(true);
    }
  }, 3000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function fetchDocs(silent: boolean = false) {
  if (!silent) loading.value = true;
  try {
    const res = await documentApi.list(props.kbId);
    documents.value = res.data.data;
    startPolling();
  } finally {
    if (!silent) loading.value = false;
  }
}

function triggerUpload() {
  fileInput.value?.click();
}

async function handleUpload(event: Event) {
  const files = (event.target as HTMLInputElement).files;
  if (!files || files.length === 0) return;
  await uploadFiles(Array.from(files));
  (event.target as HTMLInputElement).value = "";
}

async function handleDrop(event: DragEvent) {
  dragover.value = false;
  const files = event.dataTransfer?.files;
  if (!files || files.length === 0) return;
  await uploadFiles(Array.from(files));
}

async function uploadFiles(files: File[]) {
  loading.value = true;
  for (const file of files) {
    try {
      await documentApi.upload(props.kbId, file);
    } catch (e: any) {
      alert("Upload failed: " + (e.response?.data?.message || e.message));
    }
  }
  emit('uploaded');
  await fetchDocs();
}

async function deleteDoc(id: number) {
  if (!confirm("Delete this document?")) return;
  await documentApi.delete(id);
  documents.value = documents.value.filter((d) => d.id !== id);
  emit('uploaded');
}

function formatSize(bytes: number): string {
  if (!bytes) return "";
  if (bytes < 1024) return bytes + "B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + "KB";
  return (bytes / 1048576).toFixed(1) + "MB";
}

function statusClass(status: string) {
  switch (status) {
    case "COMPLETED": return "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400";
    case "PROCESSING":
    case "PARSING": return "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 animate-pulse";
    case "FAILED": return "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400";
    default: return "bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400";
  }
}
</script>
