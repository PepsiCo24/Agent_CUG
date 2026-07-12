import { defineStore } from "pinia";
import { ref } from "vue";
import { chatApi } from "@/api/chat";
import type { ChatMessage, ChatResponse } from "@/types";

export const useChatStore = defineStore("chat", () => {
  const messages = ref<ChatMessage[]>([]);
  const sending = ref(false);
  const error = ref<string | null>(null);

  async function sendMessage(kbId: number, question: string): Promise<ChatResponse | null> {
    sending.value = true;
    error.value = null;

    messages.value.push({
      id: Date.now(),
      role: "USER",
      content: question,
      citations: "[]",
      createdAt: new Date().toISOString(),
    });

    try {
      const res = await chatApi.chat(kbId, { question });
      const data = res.data.data;

      messages.value.push({
        id: Date.now() + 1,
        role: "ASSISTANT",
        content: data.answer,
        citations: JSON.stringify(data.citations),
        createdAt: new Date().toISOString(),
      });

      return data;
    } catch (e: any) {
      const msg = e.response?.data?.message || e.message || "Chat failed";
      error.value = msg;
      messages.value = messages.value.filter(m => m.content !== question || m.role !== "USER");
      return null;
    } finally {
      sending.value = false;
    }
  }

  async function fetchHistory(kbId: number) {
    try {
      const res = await chatApi.history(kbId, 0, 100);
      messages.value = (Array.isArray(res.data.data) ? res.data.data : []).reverse();
    } catch {
      messages.value = [];
    }
  }

  function clearMessages() {
    messages.value = [];
    error.value = null;
  }

  return { messages, sending, error, sendMessage, fetchHistory, clearMessages };
});
