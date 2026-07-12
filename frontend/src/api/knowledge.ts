import api from "./index";
import type { ApiResponse, KnowledgeBase, KnowledgeBaseDTO } from "@/types";

export const knowledgeApi = {
  list: () => api.get<ApiResponse<KnowledgeBase[]>>("/knowledge-bases"),

  get: (id: number) => api.get<ApiResponse<KnowledgeBase>>(`/knowledge-bases/${id}`),

  create: (data: KnowledgeBaseDTO) =>
    api.post<ApiResponse<KnowledgeBase>>("/knowledge-bases", data),

  update: (id: number, data: KnowledgeBaseDTO) =>
    api.put<ApiResponse<KnowledgeBase>>(`/knowledge-bases/${id}`, data),

  delete: (id: number) => api.delete<ApiResponse<void>>(`/knowledge-bases/${id}`),
};