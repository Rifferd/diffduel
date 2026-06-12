<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query';
import { topicsApi } from '@/shared/api/endpoints';
import AppNav from '@/components/AppNav.vue';
import TabBar from '@/components/TabBar.vue';

const { data: topics } = useQuery({
  queryKey: ['topics'],
  queryFn: () => topicsApi.list(),
});
</script>

<template>
  <div class="app">
    <AppNav active="training" />

    <main class="app__main">
      <div class="wrap">
        <div class="page-head">
          <h1>Тренировка</h1>
          <p>Решайте задачи без рейтинга и в своём темпе. Выберите тему, чтобы начать.</p>
        </div>

        <div class="section">
          <div class="grid-3">
            <div v-for="topic in topics ?? []" :key="topic.id" class="surface pad-lg">
              <h2 style="font: 700 16px var(--font-display); font-stretch: 110%">
                {{ topic.title }}
              </h2>
              <p style="color: var(--ink-soft); font-size: 14px; margin: 6px 0 14px">
                Тренировочные задачи по теме «{{ topic.title }}».
              </p>
              <button class="btn btn--ghost" type="button" disabled>Скоро</button>
            </div>
          </div>
        </div>
        <div style="height: 24px"></div>
      </div>
    </main>

    <TabBar active="training" />
  </div>
</template>
