import axios from "axios";
import type { ApiResponse } from "@/types";

const api = axios.create({
  baseURL: "http://localhost:8080/api",
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