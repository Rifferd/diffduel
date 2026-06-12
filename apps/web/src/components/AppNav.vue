<script setup lang="ts">
import { RouterLink } from 'vue-router';

defineProps<{ active: 'home' | 'training' | 'leaderboard' | 'profile' }>();
</script>

<template>
  <nav class="appnav">
    <div class="wrap appnav__in">
      <RouterLink class="nav__logo" to="/"><span class="vs">VS</span>DiffDuel</RouterLink>
      <span class="appnav__sp"></span>
      <RouterLink class="appnav__link" :class="{ 'is-on': active === 'home' }" to="/"
        >Дуэль</RouterLink
      >
      <RouterLink class="appnav__link" :class="{ 'is-on': active === 'training' }" to="/training"
        >Тренировка</RouterLink
      >
      <a class="appnav__link" href="#" @click.prevent>Рейтинг</a>
      <RouterLink class="appnav__link" :class="{ 'is-on': active === 'profile' }" to="/profile"
        >Профиль</RouterLink
      >
      <RouterLink class="appnav__link" to="/settings" aria-label="Настройки">⚙</RouterLink>
    </div>
  </nav>
</template>
