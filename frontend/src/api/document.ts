import api from "./index";
import type { ApiResponse, Document } from "@/types";

export const documentApi = {
  list: (kbId: number) =>
    api.get<ApiResponse<Document[]>>(`/documents/kb/${kbId}`),

  search: (kbId: number, keyword: string) =>
    api.get<ApiResponse<Document[]>>(`/documents/kb/${kbId}/search`, {
      params: { keyword },
    }),

  upload: (kbId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post<ApiResponse<Document>>(`/documents/upload/${kbId}`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  get: (id: number) => api.get<ApiResponse<Document>>(`/documents/${id}`),

  delete: (id: number) => api.delete<ApiResponse<void>>(`/documents/${id}`),
};