export interface User {
  id: number;
  username: string;
  email: string;
  nickname: string;
  avatarUrl?: string;
}

export interface AuthResponse {
  token: string;
  tokenType: string;
  userId: number;
  username: string;
  nickname: string;
}

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface KnowledgeBase {
  id: number;
  name: string;
  description: string;
  documentCount: number;
  anythingllmWorkspaceSlug?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Document {
  id: number;
  fileName: string;
  originalName: string;
  fileSize: number;
  fileType: string;
  mimeType: string;
  parseStatus: "PENDING" | "PARSING" | "COMPLETED" | "FAILED";
  embeddingStatus: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  markdownContent?: string;
  anythingllmDocId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ChatMessage {
  id: number;
  role: "USER" | "ASSISTANT";
  content: string;
  citations: string;
  createdAt: string;
}

export interface Citation {
  documentName: string;
  snippet: string;
  pageNumber: number;
}

export interface ChatResponse {
  answer: string;
  conversationId: string;
  citations: Citation[];
  tokensUsed: number;
}

export interface KnowledgeBaseDTO {
  name: string;
  description: string;
}

export interface ChatRequest {
  question: string;
}