import axios from "axios";
import type { ApiResponse } from "@/types";

const api = axios.create({
  // 生产环境由 Nginx 将 /api 反向代理到 Spring Boot，避免公网客户端错误访问自身 localhost。
  baseURL: "/api",
  timeout: 60000,
});

// 璇锋眰鎷︽埅鍣細娣诲姞 Token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 鍝嶅簲鎷︽埅鍣細缁熶竴閿欒澶勭悊
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;
