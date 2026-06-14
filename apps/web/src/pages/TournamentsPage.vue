<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import type { TournamentStatus, TournamentSummary } from '@diffduel/contracts';
import { tournamentsApi, topicsApi } from '@/shared/api/endpoints';
import AppNav from '@/components/AppNav.vue';
import TabBar from '@/components/TabBar.vue';

const loading = ref(true);
const error = ref<string | null>(null);
const tournaments = ref<TournamentSummary[]>([]);
const topicTitles = ref<Map<string, string>>(new Map());

const STATUS_PILL: Record<TournamentStatus, string> = {
  active: 'pill pill--live',
  upcoming: 'pill pill--soon',
  finished: 'pill pill--done',
};

const STATUS_LABEL: Record<TournamentStatus, string> = {
  active: 'live',
  upcoming: 'upcoming',
  finished: 'finished',
};

const CTA_LABEL: Record<TournamentStatus, string> = {
  active: 'Смотреть сетку',
  upcoming: 'Записаться',
  finished: 'Результаты',
};

function topicLabel(t: TournamentSummary): string {
  if (!t.topic_id) return 'all-lang';
  return topicTitles.value.get(t.topic_id) ?? '—';
}

/** Денежная подпись из decimal-строки: «299 ₽» / «0 ₽». */
function money(value: string): string {
  const n = Number(value);
  return `${Number.isFinite(n) ? n.toLocaleString('ru-RU') : value} ₽`;
}

function startsLabel(t: TournamentSummary): string {
  return new Date(t.starts_at).toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const hasTournaments = computed(() => tournaments.value.length > 0);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [list, topics] = await Promise.all([tournamentsApi.list(), topicsApi.list()]);
    tournaments.value = list;
    topicTitles.value = new Map(topics.map((tp) => [tp.id, tp.title]));
  } catch {
    error.value = 'Не удалось загрузить турниры. Проверьте соединение и попробуйте снова.';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void load();
});
</script>

<template>
  <div class="app">
    <AppNav active="tournaments" />

    <main class="app__main">
      <div class="wrap">
        <div class="page-head">
          <span class="eyebrow">// каждую неделю · бесплатные и призовые</span>
          <h1>Турниры</h1>
        </div>

        <div v-if="loading" class="section">
          <div class="surface" style="padding: 24px; text-align: center; color: var(--ink-soft)">
            Загружаем турниры…
          </div>
        </div>

        <div v-else-if="error" class="section">
          <div class="surface" style="padding: 24px">
            <p style="color: var(--minus); font-size: 14px">{{ error }}</p>
            <div style="display: flex; justify-content: flex-end; margin-top: 16px">
              <button class="btn btn--duel" type="button" @click="load">Повторить</button>
            </div>
          </div>
        </div>

        <div v-else-if="hasTournaments" class="section">
          <div class="grid-2">
            <div v-for="t in tournaments" :key="t.id" class="surface trn">
              <div class="trn__top">
                <span class="trn__name">{{ t.title }} · {{ topicLabel(t) }}</span>
                <span :class="STATUS_PILL[t.status]">
                  <span v-if="t.status === 'active'" class="live-dot"></span>
                  {{ STATUS_LABEL[t.status] }}
                </span>
              </div>
              <div class="trn__meta">
                <span><b class="t-timer">{{ startsLabel(t) }}</b>старт</span>
                <span><b>{{ t.entries_count }}</b>участников</span>
                <span><b>{{ money(t.entry_fee) }}</b>взнос</span>
                <span><b>{{ money(t.prize_pool) }}</b>фонд</span>
              </div>
              <RouterLink
                class="btn btn--block"
                :class="t.status === 'active' ? 'btn--duel' : 'btn--ghost'"
                :to="`/tournaments/${t.id}`"
              >
                {{ CTA_LABEL[t.status] }}
              </RouterLink>
            </div>
          </div>
        </div>

        <div v-else class="section">
          <span class="eyebrow">// состояние: турниров нет</span>
          <div class="surface" style="margin-top: 8px">
            <div class="empty">
              <div class="empty__icon">⌛</div>
              <div class="empty__title">Пока без турниров</div>
              <div class="empty__text">
                Новые турниры публикуются по понедельникам. Включите уведомления, чтобы не
                пропустить.
              </div>
            </div>
          </div>
        </div>
        <div style="height: 24px"></div>
      </div>
    </main>

    <TabBar active="tournaments" />
  </div>
</template>

<style scoped>
.trn {
  padding: 20px;
  display: grid;
  gap: 14px;
}
.trn__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.trn__name {
  font: 700 18px var(--font-display);
  font-stretch: 110%;
}
.trn__meta {
  display: flex;
  gap: 20px;
  font: 500 12px var(--font-mono);
  color: var(--ink-soft);
  flex-wrap: wrap;
}
.trn__meta b {
  display: block;
  font: 700 16px var(--font-mono);
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--timer);
  display: inline-block;
  animation: dd-pulse 1.2s infinite;
}
@media (prefers-reduced-motion: reduce) {
  .live-dot {
    animation: none;
  }
}
</style>
