<template>
  <div class="flex h-screen overflow-hidden">
    <Sidebar />
    <div class="flex-1 flex flex-col min-w-0">
      <TopBar />
      <main class="flex-1 overflow-hidden">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import Sidebar from "@/components/common/Sidebar.vue";
import TopBar from "@/components/common/TopBar.vue";

const authStore = useAuthStore();
const router = useRouter();

onMounted(() => {
  if (!authStore.isAuthenticated) {
    router.push("/login");
  }
});
</script>
