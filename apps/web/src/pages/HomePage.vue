<script setup lang="ts">
import { computed, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { useQuery } from '@tanstack/vue-query';
import { topicsApi } from '@/shared/api/endpoints';
import { useAuthStore } from '@/stores/auth';
import AppNav from '@/components/AppNav.vue';
import TabBar from '@/components/TabBar.vue';

const auth = useAuthStore();

const username = computed(() => auth.user?.username ?? 'игрок');
const avatarInitials = computed(() => username.value.slice(0, 2).toUpperCase());

const { data: topics } = useQuery({
  queryKey: ['topics'],
  queryFn: () => topicsApi.list(),
});

const selectedTopic = ref<string | null>(null);
const activeTopic = computed(() => {
  const list = topics.value ?? [];
  return list.find((t) => t.slug === selectedTopic.value) ?? list[0] ?? null;
});
const activeTopicTitle = computed(() => activeTopic.value?.title ?? 'SQL');
/** Slug темы для перехода в очередь («В бой»). */
const activeTopicSlug = computed(() => activeTopic.value?.slug ?? 'sql');

function selectTopic(slug: string): void {
  selectedTopic.value = slug;
}
</script>

<template>
  <div class="app">
    <AppNav active="home" />

    <main class="app__main">
      <div class="wrap">
        <div class="hi">
          <div class="hi__who">
            <h1>Привет, {{ username }}</h1>
            <span>Арена ждёт</span>
          </div>
          <span class="ava ava--you">{{ avatarInitials }}</span>
        </div>

        <div class="home-grid">
          <div class="col">
            <div class="big-cta">
              <span class="eyebrow eyebrow--arena">// 1×1 по коду</span>
              <h2 style="margin-top: 6px">Дуэль 1×1</h2>
              <p>Соперник найдётся примерно за 20 секунд</p>
              <div class="chips">
                <button
                  v-for="(topic, i) in topics ?? []"
                  :key="topic.id"
                  class="chip"
                  :class="{ 'is-on': selectedTopic === topic.slug || (!selectedTopic && i === 0) }"
                  type="button"
                  @click="selectTopic(topic.slug)"
                >
                  {{ topic.title }}
                </button>
              </div>
              <RouterLink
                class="btn btn--duel btn--block"
                :to="{ path: '/queue', query: { topic: activeTopicSlug } }"
                >В бой · {{ activeTopicTitle }}</RouterLink
              >
            </div>

            <RouterLink class="btn btn--ghost btn--block" to="/training" style="text-decoration: none"
              >Тренировка без рейтинга</RouterLink
            >
          </div>

          <div class="col">
            <div class="card daily">
              <div class="daily__ic">!</div>
              <div>
                <b>Задача дня</b><span>Новая задача каждый день</span>
              </div>
              <RouterLink class="daily__go" to="/training">Решить →</RouterLink>
            </div>

            <div class="card">
              <div class="card__head"><h3>Последние дуэли</h3></div>
              <div class="empty">
                <div class="empty__icon">∅</div>
                <div class="empty__title">Дуэлей пока нет</div>
                <div class="empty__text">
                  Сыграйте первую — соперник найдётся примерно за 20 секунд.
                </div>
                <RouterLink
                  class="btn btn--duel"
                  :to="{ path: '/queue', query: { topic: activeTopicSlug } }"
                  >В бой</RouterLink
                >
              </div>
            </div>
          </div>
        </div>
        <div style="height: 24px"></div>
      </div>
    </main>

    <TabBar active="home" />
  </div>
</template>

<style scoped>
.hi {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 22px 0 18px;
}
.hi__who h1 {
  font: 800 22px var(--font-display);
  font-stretch: 110%;
  display: block;
}
.hi__who span {
  font: 500 12px var(--font-mono);
  color: var(--ink-soft);
  font-variant-numeric: tabular-nums;
}
.home-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}
.col {
  display: grid;
  gap: 12px;
}
.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  position: relative;
  z-index: 1;
  margin-bottom: 12px;
}
.chip {
  border: 1px solid var(--arena-line);
  background: transparent;
  color: var(--arena-soft);
  border-radius: var(--radius-pill);
  padding: 6px 14px;
  font: 600 12px var(--font-body);
  cursor: pointer;
  transition: 0.12s;
}
.chip.is-on {
  background: rgb(31 157 85 / 0.16);
  border-color: var(--plus);
  color: var(--plus-bright);
}
.chip:hover {
  color: var(--arena-ink);
}
.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 16px;
  box-shadow: var(--shadow-card);
}
.card__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.card__head h3 {
  font: 700 16px var(--font-display);
  font-stretch: 110%;
}
.daily {
  display: flex;
  gap: 12px;
  align-items: center;
}
.daily__ic {
  width: 42px;
  height: 42px;
  border-radius: var(--radius);
  background: var(--plus-bg);
  display: grid;
  place-items: center;
  font: 700 15px var(--font-mono);
  color: var(--plus);
  flex: none;
}
.daily b {
  font-size: 14px;
}
.daily span {
  display: block;
  font-size: 12px;
  color: var(--ink-soft);
}
.daily__go {
  margin-left: auto;
  font: 700 13px var(--font-mono);
  color: var(--plus);
  text-decoration: none;
}
@media (max-width: 640px) {
  .home-grid {
    grid-template-columns: 1fr;
  }
  .hi__who h1 {
    font-size: 18px;
  }
}
</style>
