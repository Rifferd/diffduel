<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useQuery } from '@tanstack/vue-query';
import type { TopicPublic } from '@diffduel/contracts';
import { topicsApi } from '@/shared/api/endpoints';
import AppNav from '@/components/AppNav.vue';
import TabBar from '@/components/TabBar.vue';

const router = useRouter();

const DIFFICULTIES = [
  { value: 1, label: '1 · база' },
  { value: 2, label: '2 · средне' },
  { value: 3, label: '3 · хард' },
] as const;

const difficulty = ref<number>(1);

const { data: topics } = useQuery({
  queryKey: ['topics'],
  queryFn: () => topicsApi.list(),
});

/** Короткий код темы для аватарки (как SQL/JS/PY в макете). */
function topicAbbr(topic: TopicPublic): string {
  const map: Record<string, string> = { sql: 'SQL', javascript: 'JS', python: 'PY' };
  return map[topic.slug] ?? topic.title.slice(0, 2).toUpperCase();
}

function startTraining(topic: TopicPublic): void {
  router.push({
    path: '/training/run',
    query: { topic: topic.slug, difficulty: String(difficulty.value) },
  });
}
</script>

<template>
  <div class="app">
    <AppNav active="training" />

    <main class="app__main">
      <div class="wrap">
        <div class="page-head">
          <span class="eyebrow">// без рейтинга · в своём темпе</span>
          <h1>Тренировка</h1>
          <p>
            Отрабатывай слабые темы без давления Эло. Прогресс считается по доле верных ответов.
          </p>
        </div>

        <div class="section">
          <div class="section__head">
            <h2>Сложность</h2>
            <div class="seg" role="tablist" aria-label="Сложность">
              <button
                v-for="opt in DIFFICULTIES"
                :key="opt.value"
                class="seg__opt"
                :class="{ 'is-on': difficulty === opt.value }"
                role="tab"
                :aria-selected="difficulty === opt.value"
                type="button"
                @click="difficulty = opt.value"
              >
                {{ opt.label }}
              </button>
            </div>
          </div>

          <div class="grid-3">
            <div v-for="topic in topics ?? []" :key="topic.id" class="surface topic-card">
              <div class="topic-card__top">
                <span class="topic-card__name">{{ topic.title }}</span>
                <span class="ava ava--1 ava--sm">{{ topicAbbr(topic) }}</span>
              </div>
              <button class="btn btn--duel btn--block" type="button" @click="startTraining(topic)">
                Тренироваться
              </button>
            </div>
          </div>
        </div>
        <div style="height: 24px"></div>
      </div>
    </main>

    <TabBar active="training" />
  </div>
</template>

<style scoped>
.topic-card {
  display: grid;
  gap: 14px;
  padding: 20px;
}
.topic-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.topic-card__name {
  font: 700 18px var(--font-display);
  font-stretch: 110%;
}
</style>
