<script setup lang="ts">
import { RouterLink } from 'vue-router';

withDefaults(
  defineProps<{
    /** Заголовок пейволла — какая Pro-функция закрыта. */
    title?: string;
    /** Поясняющий текст. */
    text?: string;
  }>(),
  {
    title: 'Это функция DiffDuel Pro',
    text: 'Оформите Pro, чтобы открыть AI-разбор ошибок и расширенную статистику слабых тем.',
  },
);
</script>

<template>
  <div class="surface paywall">
    <span class="eyebrow eyebrow--accent">// только для Pro</span>
    <h2 class="paywall__title">{{ title }}</h2>
    <p class="paywall__text">{{ text }}</p>
    <RouterLink class="btn btn--duel" to="/pro">Узнать о Pro</RouterLink>
  </div>
</template>

<style scoped>
.paywall {
  padding: 28px 22px;
  display: grid;
  gap: 10px;
  justify-items: center;
  text-align: center;
}
.paywall__title {
  font: 800 22px var(--font-display);
  font-stretch: 110%;
}
.paywall__text {
  font-size: 14px;
  color: var(--ink-soft);
  line-height: 1.6;
  max-width: 420px;
}
.paywall .btn {
  margin-top: 6px;
}
</style>
