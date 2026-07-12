import { defineStore } from "pinia";
import { ref } from "vue";
import { knowledgeApi } from "@/api/knowledge";
import type { KnowledgeBase, KnowledgeBaseDTO } from "@/types";

export const useKnowledgeStore = defineStore("knowledge", () => {
  const knowledgeBases = ref<KnowledgeBase[]>([]);
  const currentKB = ref<KnowledgeBase | null>(null);
  const loading = ref(false);

  async function fetchList() {
    loading.value = true;
    try {
      const res = await knowledgeApi.list();
      knowledgeBases.value = res.data.data;
    } finally {
      loading.value = false;
    }
  }

  async function create(dto: KnowledgeBaseDTO) {
    const res = await knowledgeApi.create(dto);
    await fetchList();
    return res.data.data;
  }

  async function update(id: number, dto: KnowledgeBaseDTO) {
    const res = await knowledgeApi.update(id, dto);
    await fetchList();
    return res.data.data;
  }

  async function remove(id: number) {
    await knowledgeApi.delete(id);
    await fetchList();
  }

  async function fetchById(id: number) {
    const res = await knowledgeApi.get(id);
    currentKB.value = res.data.data;
    return currentKB.value;
  }

  return { knowledgeBases, currentKB, loading, fetchList, create, update, remove, fetchById };
});