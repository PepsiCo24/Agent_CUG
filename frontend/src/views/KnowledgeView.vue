<template>
  <div class="h-full flex flex-col">
    <div v-if="!kbStore.currentKB" class="flex-1 flex items-center justify-center">
      <div class="text-center animate-fade-in">
        <Database :size="40" class="mx-auto text-gray-300 dark:text-gray-600 mb-3" />
        <p class="text-gray-400">Select a knowledge base from the sidebar</p>
      </div>
    </div>

    <template v-else>
      <!-- Header bar -->
      <div class="flex-shrink-0 flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gpt-main-dark">
        <div class="flex items-center gap-2">
          <Database :size="16" class="text-gpt-accent" />
          <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ kbStore.currentKB.name }}</span>
          <span class="text-xs text-gray-400">{{ kbStore.currentKB.documentCount }} docs</span>
        </div>
        <div class="flex items-center gap-2">
          <button @click="clearChatHistory" class="text-xs text-gray-400 hover:text-red-500 transition-colors flex items-center gap-1">
            <Trash2 :size="12" /> Clear history
          </button>
        </div>
      </div>

      <!-- Messages -->
      <div ref="messagesContainer" class="flex-1 overflow-y-auto">
        <div v-if="chatStore.messages.length === 0" class="h-full flex items-center justify-center">
          <div class="text-center animate-fade-in">
            <div class="w-16 h-16 rounded-2xl bg-gpt-accent/10 flex items-center justify-center mx-auto mb-4">
              <MessageCircle :size="32" class="text-gpt-accent" />
            </div>
            <h3 class="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">{{ kbStore.currentKB.name }}</h3>
            <p class="text-sm text-gray-400 mb-1">Documents: {{ kbStore.currentKB.documentCount }}</p>
            <p class="text-sm text-gray-400">Ask questions about your documents</p>
          </div>
        </div>

        <div v-else class="max-w-3xl mx-auto px-4 py-6 space-y-6">
          <div v-for="msg in chatStore.messages" :key="msg.id" class="animate-slide-up">
            <div v-if="msg.role === 'USER'" class="flex justify-end">
              <div class="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-br-md bg-gpt-user-msg dark:bg-gpt-user-msg-dark text-gray-900 dark:text-gray-100">
                <p class="text-sm whitespace-pre-wrap">{{ msg.content }}</p>
              </div>
            </div>
            <div v-else class="flex gap-3">
              <div class="w-7 h-7 rounded-full bg-gpt-accent/20 flex-shrink-0 flex items-center justify-center mt-0.5">
                <Sparkles :size="14" class="text-gpt-accent" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="markdown-content text-sm text-gray-800 dark:text-gray-200" v-html="renderMarkdown(msg.content)"></div>
                <div v-if="getCitations(msg).length > 0" class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                  <p class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Sources</p>
                  <div class="space-y-1.5">
                    <div v-for="(cite, idx) in getCitations(msg)" :key="idx" class="flex items-start gap-2 p-2 rounded-gpt bg-gray-50 dark:bg-gray-800/50 text-xs">
                      <FileText :size="12" class="flex-shrink-0 mt-0.5 text-gray-400" />
                      <div class="min-w-0">
                        <span class="font-medium text-gray-700 dark:text-gray-300">{{ cite.documentName }}</span>
                        <span v-if="cite.pageNumber" class="text-gray-400"> | Page {{ cite.pageNumber }}</span>
                        <p class="text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">{{ cite.snippet }}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Error message -->
          <div v-if="chatStore.error" class="flex justify-center">
            <div class="px-4 py-2 rounded-gpt bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm">
              {{ chatStore.error }}
              <button @click="chatStore.error = null" class="ml-2 underline">Dismiss</button>
            </div>
          </div>

          <!-- Loading indicator -->
          <div v-if="chatStore.sending" class="flex gap-3 animate-fade-in">
            <div class="w-7 h-7 rounded-full bg-gpt-accent/20 flex-shrink-0 flex items-center justify-center">
              <Sparkles :size="14" class="text-gpt-accent" />
            </div>
            <div class="flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-gpt-accent animate-bounce" style="animation-delay: 0ms"></span>
              <span class="w-2 h-2 rounded-full bg-gpt-accent animate-bounce" style="animation-delay: 150ms"></span>
              <span class="w-2 h-2 rounded-full bg-gpt-accent animate-bounce" style="animation-delay: 300ms"></span>
            </div>
          </div>
        </div>
      </div>

      <!-- Chat input -->
      <div class="flex-shrink-0 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gpt-main-dark p-4">
        <div class="max-w-3xl mx-auto">
          <div class="flex gap-3">
            <textarea
              v-model="question"
              class="input-field resize-none"
              rows="1"
              placeholder="Ask a question about your documents..."
              :disabled="chatStore.sending"
              @keydown.enter.exact.prevent="sendMessage"
              @input="autoResize"
              ref="inputEl"
            />
            <button @click="sendMessage" class="btn-primary p-2.5 self-end flex-shrink-0" :disabled="!question.trim() || chatStore.sending">
              <Send :size="16" />
            </button>
          </div>

          <div class="mt-2 flex items-center justify-between">
            <p class="text-xs text-gray-400">{{ kbStore.currentKB.documentCount }} documents | Shift+Enter for new line</p>
            <button @click="showDocs = !showDocs" class="text-xs text-gpt-accent hover:underline flex items-center gap-1">
              <FolderOpen :size="12" /> {{ showDocs ? 'Hide' : 'Manage' }} Documents
            </button>
          </div>

          <!-- Document management panel -->
          <div v-if="showDocs" class="mt-3 animate-slide-up">
            <DocumentList :kb-id="Number(route.params.id)" :refresh-key="docRefreshKey" @uploaded="onDocUploaded" />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from "vue";
import { useRoute } from "vue-router";
import { useChatStore } from "@/stores/chat";
import { useKnowledgeStore } from "@/stores/knowledge";
import DocumentList from "@/components/document/DocumentList.vue";
import { MessageCircle, Sparkles, Send, FileText, FolderOpen, Database, Trash2 } from "lucide-vue-next";
import MarkdownIt from "markdown-it";
import type { Citation } from "@/types";
import { chatApi } from "@/api/chat";

const route = useRoute();
const chatStore = useChatStore();
const kbStore = useKnowledgeStore();

const question = ref("");
const showDocs = ref(true);
const docRefreshKey = ref(0);
const messagesContainer = ref<HTMLElement>();
const inputEl = ref<HTMLTextAreaElement>();

const md = new MarkdownIt({ breaks: true, linkify: true });

onMounted(async () => {
  const id = Number(route.params.id);
  if (id) {
    await kbStore.fetchById(id);
    await chatStore.fetchHistory(id);
    await scrollToBottom();
  }
});

watch(() => route.params.id, async (newId) => {
  if (newId) {
    chatStore.clearMessages();
    await kbStore.fetchById(Number(newId));
    await chatStore.fetchHistory(Number(newId));
    await scrollToBottom();
  }
});

watch(() => chatStore.messages.length, async () => { await scrollToBottom(); });

function autoResize() {
  nextTick(() => {
    if (inputEl.value) {
      inputEl.value.style.height = "auto";
      inputEl.value.style.height = Math.min(inputEl.value.scrollHeight, 200) + "px";
    }
  });
}

async function scrollToBottom() {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
}

async function sendMessage() {
  if (!question.value.trim() || chatStore.sending) return;
  const q = question.value.trim();
  question.value = "";
  nextTick(() => { if (inputEl.value) inputEl.value.style.height = "auto"; });
  await chatStore.sendMessage(Number(route.params.id), q);
}

function onDocUploaded() {
  docRefreshKey.value++;
  kbStore.fetchById(Number(route.params.id));
}

async function clearChatHistory() {
  if (!confirm("Clear all chat history for this knowledge base?")) return;
  try {
    await chatApi.clearHistory(Number(route.params.id));
    chatStore.clearMessages();
  } catch (e: any) {
    alert("Failed to clear history");
  }
}

function renderMarkdown(content: string): string {
  return md.render(content);
}

function getCitations(msg: any): Citation[] {
  try { return JSON.parse(msg.citations || "[]"); } catch { return []; }
}
</script>
