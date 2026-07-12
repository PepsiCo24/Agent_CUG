<template>
  <aside
    class="w-64 flex-shrink-0 flex flex-col border-r border-gray-200 dark:border-gray-700
           bg-gpt-sidebar dark:bg-gpt-sidebar-dark transition-colors duration-150"
  >
    <!-- Logo -->
    <div class="flex items-center gap-2 px-4 py-3 border-b border-gray-200 dark:border-gray-700">
      <div class="w-8 h-8 rounded-lg bg-gpt-accent flex items-center justify-center">
        <span class="text-white font-bold text-sm">CG</span>
      </div>
      <span class="font-semibold text-sm text-gray-800 dark:text-gray-200">Agent CUG</span>
    </div>

    <!-- New KB Button -->
    <div class="p-3">
      <button
        v-if="!showNewKBInput"
        @click="showNewKBInput = true"
        class="w-full flex items-center gap-2 px-3 py-2.5 rounded-gpt border border-gray-200
               dark:border-gray-700 text-sm text-gray-700 dark:text-gray-300
               hover:bg-gray-100 dark:hover:bg-gray-800 transition-all duration-150"
      >
        <Plus :size="16" />
        <span>New Knowledge Base</span>
      </button>
      <div v-else class="flex gap-1.5">
        <input
          ref="newKbInput"
          v-model="newKbName"
          type="text"
          class="input-field text-sm flex-1"
          placeholder="Knowledge base name..."
          @keydown.enter="doCreateKB"
          @keydown.escape="cancelNewKB"
        />
        <button @click="doCreateKB" class="btn-primary text-xs px-2.5 py-1.5" :disabled="!newKbName.trim() || creatingKB">
          OK
        </button>
        <button @click="cancelNewKB" class="btn-secondary text-xs px-2.5 py-1.5">X</button>
      </div>
    </div>

    <!-- KB List -->
    <div class="flex-1 overflow-y-auto px-2">
      <div v-if="kbStore.loading" class="flex justify-center py-8">
        <div class="animate-pulse text-gray-400 text-sm">Loading...</div>
      </div>
      <div v-else-if="kbStore.knowledgeBases.length === 0" class="py-8 text-center">
        <Database :size="32" class="mx-auto text-gray-300 dark:text-gray-600 mb-2" />
        <p class="text-xs text-gray-400">No knowledge bases yet</p>
      </div>
      <div v-else class="space-y-0.5 py-2">
        <button
          v-for="kb in kbStore.knowledgeBases"
          :key="kb.id"
          @click="selectKB(kb.id)"
          class="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-gpt text-sm text-left
                 transition-all duration-150 group"
          :class="currentId === kb.id
            ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100'
            : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'"
        >
          <Database :size="15" class="flex-shrink-0" />
          <span class="truncate flex-1">{{ kb.name }}</span>
          <span class="text-xs text-gray-400 flex-shrink-0">{{ kb.documentCount }}</span>
          <button
            @click.stop="deleteKB(kb.id)"
            class="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-100
                   dark:hover:bg-red-900/30 text-gray-400 hover:text-red-500 transition-all"
          >
            <Trash2 :size="13" />
          </button>
        </button>
      </div>
    </div>

    <!-- User Footer -->
    <div class="p-3 border-t border-gray-200 dark:border-gray-700">
      <div class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
        <div class="w-7 h-7 rounded-full bg-gpt-accent/20 flex items-center justify-center">
          <User :size="14" class="text-gpt-accent" />
        </div>
        <span class="flex-1 truncate">{{ authStore.user?.nickname || authStore.user?.username }}</span>
        <button
          @click="logout"
          class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          title="Logout"
        >
          <LogOut :size="14" />
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, nextTick, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useKnowledgeStore } from "@/stores/knowledge";
import { Plus, Database, Trash2, User, LogOut } from "lucide-vue-next";

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const kbStore = useKnowledgeStore();

const showNewKBInput = ref(false);
const newKbName = ref("");
const creatingKB = ref(false);
const newKbInput = ref<HTMLInputElement>();

const currentId = computed(() => {
  const id = route.params.id;
  return id ? Number(id) : null;
});

onMounted(() => {
  kbStore.fetchList();
});

// Auto-focus input when shown
watch(showNewKBInput, async (val) => {
  if (val) {
    await nextTick();
    newKbInput.value?.focus();
  }
});

function selectKB(id: number) {
  router.push("/kb/" + id);
}

async function doCreateKB() {
  const name = newKbName.value.trim();
  if (!name || creatingKB.value) return;
  creatingKB.value = true;
  try {
    const kb = await kbStore.create({ name, description: "" });
    showNewKBInput.value = false;
    newKbName.value = "";
    router.push("/kb/" + kb.id);
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

async function deleteKB(id: number) {
  if (!confirm("Delete this knowledge base? This cannot be undone.")) return;
  await kbStore.remove(id);
  if (currentId.value === id) {
    router.push("/");
  }
}

function logout() {
  authStore.logout();
  router.push("/login");
}
</script>
