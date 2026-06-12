<script setup lang="ts">
import { RouterView } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
</script>

<template>
  <RouterView v-if="auth.ready" />
  <div v-else class="auth">
    <div class="auth__card">
      <span class="auth__title">DiffDuel</span>
      <p class="auth__sub">Загрузка…</p>
    </div>
  </div>
</template>
