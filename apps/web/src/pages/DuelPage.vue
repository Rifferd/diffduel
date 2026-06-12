<script setup lang="ts">
import { RouterLink } from 'vue-router';
</script>

<template>
  <main class="arena-screen">
    <div class="arena-screen__bar">
      <RouterLink class="arena-screen__logo" to="/"><span class="vs">VS</span>DiffDuel</RouterLink>
    </div>
    <div class="arena-screen__body">
      <div>
        <span class="eyebrow eyebrow--arena">// дуэль</span>
        <h1 style="font: 800 30px var(--font-display); font-stretch: 110%; margin: 8px 0 6px">
          Скоро
        </h1>
        <p style="color: var(--arena-soft); max-width: 42ch; margin: 0 auto 18px">
          Режим дуэлей 1×1 в реальном времени ещё в разработке. Загляните чуть позже.
        </p>
        <RouterLink class="btn btn--duel" to="/">На главную</RouterLink>
      </div>
    </div>
  </main>
</template>
