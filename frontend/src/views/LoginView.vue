<template>
  <div class="min-h-screen flex items-center justify-center bg-gpt-sidebar dark:bg-gpt-sidebar-dark p-4">
    <div class="w-full max-w-sm animate-slide-up">
      <!-- Logo -->
      <div class="text-center mb-8">
        <div class="w-12 h-12 rounded-xl bg-gpt-accent flex items-center justify-center mx-auto mb-3">
          <span class="text-white font-bold text-xl">CG</span>
        </div>
        <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">Agent CUG</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">智能知识库系统</p>
      </div>

      <!-- Login Form -->
      <div class="card p-6">
        <h2 class="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">登录</h2>

        <div v-if="error" class="mb-4 p-3 rounded-gpt bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm">
          {{ error }}
        </div>

        <form @submit.prevent="handleLogin" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">用户名</label>
            <input
              v-model="form.username"
              type="text"
              class="input-field"
              placeholder="请输入用户名"
              required
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">密码</label>
            <input
              v-model="form.password"
              type="password"
              class="input-field"
              placeholder="请输入密码"
              required
            />
          </div>
          <button
            type="submit"
            class="btn-primary w-full"
            :disabled="loading"
          >
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </form>

        <p class="mt-4 text-center text-sm text-gray-500 dark:text-gray-400">
          还没有账号？
          <router-link to="/register" class="text-gpt-accent hover:underline">立即注册</router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const authStore = useAuthStore();

const loading = ref(false);
const error = ref("");
const form = reactive({ username: "", password: "" });

async function handleLogin() {
  error.value = "";
  loading.value = true;
  try {
    await authStore.login(form.username, form.password);
    router.push("/");
  } catch (e: any) {
    error.value = e.response?.data?.message || "登录失败，请重试";
  } finally {
    loading.value = false;
  }
}
</script>