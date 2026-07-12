import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { authApi } from "@/api/auth";
import type { User, AuthResponse } from "@/types";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string>(localStorage.getItem("token") || "");
  const user = ref<User | null>(null);
  const isAuthenticated = computed(() => !!token.value);

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password });
    setAuth(res.data.data);
    return res.data.data;
  }

  async function register(username: string, password: string, email: string, nickname?: string) {
    const res = await authApi.register({ username, password, email, nickname });
    setAuth(res.data.data);
    return res.data.data;
  }

  function setAuth(data: AuthResponse) {
    token.value = data.token;
    localStorage.setItem("token", data.token);
    user.value = {
      id: data.userId,
      username: data.username,
      nickname: data.nickname,
      email: "",
    };
  }

  function logout() {
    token.value = "";
    user.value = null;
    localStorage.removeItem("token");
  }

  return { token, user, isAuthenticated, login, register, logout };
});