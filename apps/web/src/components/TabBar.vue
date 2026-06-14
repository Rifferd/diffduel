<script setup lang="ts">
import { RouterLink } from 'vue-router';

defineProps<{ active: 'home' | 'training' | 'daily' | 'leaderboard' | 'profile' }>();
</script>

<template>
  <nav class="tabbar">
    <RouterLink class="tabbar__tab" :class="{ 'is-on': active === 'home' }" to="/app">
      <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M13 2 4 14h6l-1 8 9-12h-6z" /></svg>
      Дуэль
    </RouterLink>
    <RouterLink class="tabbar__tab" :class="{ 'is-on': active === 'training' }" to="/training">
      <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 20V10M6 20V4M18 20v-7" /></svg>
      Тренировка
    </RouterLink>
    <RouterLink class="tabbar__tab" :class="{ 'is-on': active === 'daily' }" to="/daily">
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </svg>
      День
    </RouterLink>
    <a class="tabbar__tab" href="#" @click.prevent>
      <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 19V5m6 14V9m6 10v-7" /></svg>
      Рейтинг
    </a>
    <RouterLink class="tabbar__tab" :class="{ 'is-on': active === 'profile' }" to="/profile">
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21c1.5-4 5-5 8-5s6.5 1 8 5" />
      </svg>
      Профиль
    </RouterLink>
  </nav>
</template>
