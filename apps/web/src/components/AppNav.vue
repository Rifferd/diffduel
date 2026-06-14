<script setup lang="ts">
import { RouterLink } from 'vue-router';

defineProps<{
  active: 'home' | 'training' | 'daily' | 'tournaments' | 'leaderboard' | 'profile' | 'pro';
}>();
</script>

<template>
  <nav class="appnav">
    <div class="wrap appnav__in">
      <RouterLink class="nav__logo" to="/app"><span class="vs">VS</span>DiffDuel</RouterLink>
      <span class="appnav__sp"></span>
      <RouterLink class="appnav__link" :class="{ 'is-on': active === 'home' }" to="/app"
        >Дуэль</RouterLink
      >
      <RouterLink class="appnav__link" :class="{ 'is-on': active === 'training' }" to="/training"
        >Тренировка</RouterLink
      >
      <RouterLink class="appnav__link" :class="{ 'is-on': active === 'daily' }" to="/daily"
        >Задача дня</RouterLink
      >
      <RouterLink
        class="appnav__link"
        :class="{ 'is-on': active === 'tournaments' }"
        to="/tournaments"
        >Турниры</RouterLink
      >
      <a class="appnav__link" href="#" @click.prevent>Рейтинг</a>
      <RouterLink class="appnav__link" :class="{ 'is-on': active === 'pro' }" to="/pro"
        >Pro</RouterLink
      >
      <RouterLink class="appnav__link" :class="{ 'is-on': active === 'profile' }" to="/profile"
        >Профиль</RouterLink
      >
      <RouterLink class="appnav__link" to="/settings" aria-label="Настройки">⚙</RouterLink>
    </div>
  </nav>
</template>
