import api from "./index";
import type { ApiResponse, ChatMessage, ChatResponse, ChatRequest } from "@/types";

export const chatApi = {
  chat: (kbId: number, data: ChatRequest) =>
    api.post<ApiResponse<ChatResponse>>("/chat/" + kbId, data),

  history: (kbId: number, page = 0, size = 20) =>
    api.get<ApiResponse<{ content: ChatMessage[]; totalPages: number }>>(
      "/chat/" + kbId + "/history",
      { params: { page, size } }
    ),

  clearHistory: (kbId: number) =>
    api.delete<ApiResponse<void>>("/chat/" + kbId + "/history"),
};