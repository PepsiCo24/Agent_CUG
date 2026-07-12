<template>
  <header
    class="h-12 flex items-center justify-between px-4 border-b border-gray-200 dark:border-gray-700
           bg-white dark:bg-gpt-main-dark flex-shrink-0"
  >
    <div class="text-sm font-medium text-gray-700 dark:text-gray-300">
      {{ title }}
    </div>
    <div class="flex items-center gap-1">
      <button
        @click="toggleDark()"
        class="btn-ghost p-2"
        :title="isDark ? '切换到亮色模式' : '切换到暗色模式'"
      >
        <Sun v-if="isDark" :size="16" />
        <Moon v-else :size="16" />
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useKnowledgeStore } from "@/stores/knowledge";
import { useDarkMode } from "@/composables/useDarkMode";
import { Sun, Moon } from "lucide-vue-next";

const route = useRoute();
const kbStore = useKnowledgeStore();
const { isDark, toggleDark } = useDarkMode();

const title = computed(() => {
  if (kbStore.currentKB) {
    return kbStore.currentKB.name;
  }
  if (route.name === "Home") return "Agent CUG - 智能知识库系统";
  return "Agent CUG";
});
</script>
