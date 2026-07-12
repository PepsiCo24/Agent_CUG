<template>
  <div class="h-full flex items-center justify-center p-8">
    <div class="text-center max-w-lg animate-fade-in">
      <div class="w-20 h-20 rounded-2xl bg-gpt-accent/10 flex items-center justify-center mx-auto mb-6">
        <Database :size="40" class="text-gpt-accent" />
      </div>
      <h2 class="text-2xl font-semibold text-gray-800 dark:text-gray-200 mb-3">
        欢迎使用 Agent CUG
      </h2>
      <p class="text-gray-500 dark:text-gray-400 mb-8 leading-relaxed">
        基于 RAG 的智能知识库系统。<br />
        上传文档，自动解析，构建知识库，然后提问 —— AI 帮你找到答案。
      </p>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div class="card p-4 text-left">
          <FileText :size="20" class="text-gpt-accent mb-2" />
          <h3 class="text-sm font-semibold mb-1">上传文档</h3>
          <p class="text-xs text-gray-500 dark:text-gray-400">支持 PDF、Word、Markdown 等多种格式</p>
        </div>
        <div class="card p-4 text-left">
          <Brain :size="20" class="text-gpt-accent mb-2" />
          <h3 class="text-sm font-semibold mb-1">智能解析</h3>
          <p class="text-xs text-gray-500 dark:text-gray-400">自动分块、向量化、构建索引</p>
        </div>
        <div class="card p-4 text-left">
          <MessageCircle :size="20" class="text-gpt-accent mb-2" />
          <h3 class="text-sm font-semibold mb-1">RAG 问答</h3>
          <p class="text-xs text-gray-500 dark:text-gray-400">基于文档的精准回答，带引用来源</p>
        </div>
      </div>

      <div v-if="!showNewKBInput">
        <button
          @click="showNewKBInput = true"
          class="btn-primary inline-flex items-center gap-2"
        >
          <Plus :size="16" />
          创建你的第一个知识库
        </button>
      </div>
      <div v-else class="flex gap-2 justify-center">
        <input
          ref="newKbInput"
          v-model="newKbName"
          type="text"
          class="input-field text-sm max-w-xs"
          placeholder="知识库名称..."
          @keydown.enter="doCreateKB"
          @keydown.escape="cancelNewKB"
        />
        <button @click="doCreateKB" class="btn-primary text-sm" :disabled="!newKbName.trim() || creatingKB">
          创建
        </button>
        <button @click="cancelNewKB" class="btn-secondary text-sm">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from "vue";
import { useRouter } from "vue-router";
import { useKnowledgeStore } from "@/stores/knowledge";
import { Database, FileText, Brain, MessageCircle, Plus } from "lucide-vue-next";

const router = useRouter();
const kbStore = useKnowledgeStore();

const showNewKBInput = ref(false);
const newKbName = ref("");
const creatingKB = ref(false);
const newKbInput = ref<HTMLInputElement>();

watch(showNewKBInput, async (val) => {
  if (val) {
    await nextTick();
    newKbInput.value?.focus();
  }
});

async function doCreateKB() {
  const name = newKbName.value.trim();
  if (!name || creatingKB.value) return;
  creatingKB.value = true;
  try {
    const kb = await kbStore.create({ name, description: "" });
    showNewKBInput.value = false;
    newKbName.value = "";
    router.push(`/kb/${kb.id}`);
  } catch (e: any) {
    alert(e.response?.data?.message || "Failed to create knowledge base");
  } finally {
    creatingKB.value = false;
  }
}

function cancelNewKB() {
  showNewKBInput.value = false;
  newKbName.value = "";
}
</script>
