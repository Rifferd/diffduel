<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import type { TournamentDetail, TournamentStatus } from '@diffduel/contracts';
import { tournamentsApi } from '@/shared/api/endpoints';
import { ApiRequestError } from '@/shared/api/client';
import { useAuthStore } from '@/stores/auth';
import { useTournamentSession } from '@/composables/useTournamentSession';

const route = useRoute();
const auth = useAuthStore();
const tournamentId = computed(() => String(route.params.id ?? ''));
const myUserId = computed(() => auth.user?.id ?? null);

const loading = ref(true);
const loadError = ref<string | null>(null);
const tournament = ref<TournamentDetail | null>(null);

/** Текущий пользователь — участник (есть в лидерборде). */
const isParticipant = computed(() => {
  const t = tournament.value;
  if (!t || !myUserId.value) return false;
  return t.leaderboard.some((e) => e.user_id === myUserId.value);
});

const status = computed<TournamentStatus | null>(() => tournament.value?.status ?? null);

const STATUS_PILL: Record<TournamentStatus, string> = {
  active: 'pill pill--live',
  upcoming: 'pill pill--soon',
  finished: 'pill pill--done',
};
const STATUS_LABEL: Record<TournamentStatus, string> = {
  active: 'live',
  upcoming: 'upcoming',
  finished: 'завершён',
};

// --- Вход в турнир ---
const entering = ref(false);
const enterMessage = ref<string | null>(null);
const enterIsError = ref(false);

async function enter(): Promise<void> {
  if (entering.value) return;
  entering.value = true;
  enterMessage.value = null;
  enterIsError.value = false;
  try {
    await tournamentsApi.enter(tournamentId.value);
    await load();
    enterMessage.value = 'Вы записаны на турнир.';
  } catch (err) {
    enterIsError.value = true;
    if (err instanceof ApiRequestError && err.code === 'entry_payment_unavailable') {
      enterMessage.value = 'Платный вход недоступен — оплата недоступна, обратитесь к админу.';
    } else if (err instanceof ApiRequestError) {
      enterMessage.value = err.message;
    } else {
      enterMessage.value = 'Не удалось записаться. Проверьте соединение и попробуйте снова.';
    }
  } finally {
    entering.value = false;
  }
}

function money(value: string): string {
  const n = Number(value);
  return `${Number.isFinite(n) ? n.toLocaleString('ru-RU') : value} ₽`;
}

async function load(): Promise<void> {
  loading.value = true;
  loadError.value = null;
  try {
    tournament.value = await tournamentsApi.detail(tournamentId.value);
  } catch {
    loadError.value = 'Не удалось загрузить турнир. Проверьте соединение и попробуйте снова.';
  } finally {
    loading.value = false;
  }
}

// --- Режим игры (turnirnaya sessiya) ---
const playing = ref(false);
const session = useTournamentSession(tournamentId.value);
const {
  phase,
  loadError: sessionLoadError,
  answerError,
  current,
  verdict,
  selected,
  submitting,
  summary,
  questionNumber,
  tasks,
  score,
} = session;

const progressPct = computed(() => {
  const total = tasks.value.length;
  if (total === 0) return 0;
  const done = phase.value === 'verdict' ? questionNumber.value : questionNumber.value - 1;
  return Math.round((done / total) * 100);
});

function optClass(optionIndex: number): Record<string, boolean> {
  if (phase.value !== 'verdict' || !verdict.value) return {};
  const isCorrectOption = optionIndex === verdict.value.correct_option;
  const isChosen = optionIndex === selected.value;
  if (verdict.value.correct) return { 'is-correct': isCorrectOption };
  return { 'is-reveal': isCorrectOption, 'is-wrong': isChosen && !isCorrectOption };
}

function optDisabled(optionIndex: number): boolean {
  if (phase.value === 'answering') return submitting.value;
  if (!verdict.value) return true;
  const isCorrectOption = optionIndex === verdict.value.correct_option;
  const isChosen = optionIndex === selected.value;
  return !(isCorrectOption || isChosen);
}

async function play(): Promise<void> {
  playing.value = true;
  await session.load();
}

function leavePlay(): void {
  playing.value = false;
  void load();
}

onMounted(() => {
  void load();
});
</script>

<template>
  <div class="app">
    <nav class="appnav">
      <div class="wrap appnav__in">
        <RouterLink class="nav__logo" to="/tournaments"
          ><span class="vs">VS</span>DiffDuel</RouterLink
        >
        <span class="appnav__sp"></span>
        <RouterLink class="appnav__link" to="/tournaments">← Все турниры</RouterLink>
      </div>
    </nav>

    <main class="app__main">
      <div class="wrap">
        <!-- Загрузка / ошибка -->
        <div v-if="loading" class="surface" style="padding: 24px; margin-top: 14px; color: var(--ink-soft)">
          Загружаем турнир…
        </div>
        <div v-else-if="loadError" class="surface" style="padding: 24px; margin-top: 14px">
          <p style="color: var(--minus); font-size: 14px">{{ loadError }}</p>
          <div style="display: flex; justify-content: flex-end; margin-top: 16px">
            <button class="btn btn--duel" type="button" @click="load">Повторить</button>
          </div>
        </div>

        <!-- Режим игры -->
        <template v-else-if="playing && tournament">
          <div class="crumbs" style="padding-top: 14px">
            <a href="#" @click.prevent="leavePlay">{{ tournament.title }}</a>
            <span class="crumbs__sep">/</span><b>игра</b>
          </div>
          <div class="run">
            <div v-if="phase === 'loading'" class="surface qcard" style="margin-top: 8px">
              <div class="qcard__label">Загружаем задачи…</div>
            </div>

            <div v-else-if="phase === 'error'" class="surface qcard" style="margin-top: 8px">
              <div class="qcard__label">Ошибка</div>
              <p style="color: var(--ink-soft); font-size: 14px">{{ sessionLoadError }}</p>
              <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 16px">
                <button class="btn btn--ghost" type="button" @click="leavePlay">Назад</button>
                <button class="btn btn--duel" type="button" @click="session.load()">Повторить</button>
              </div>
            </div>

            <template v-else-if="phase === 'summary'">
              <div class="surface summary" style="margin-top: 8px">
                <span class="eyebrow eyebrow--accent">{{ tournament.title }}</span>
                <div style="font: 800 34px var(--font-display); font-stretch: 110%">
                  {{ summary?.correct ?? 0 }} / {{ summary?.total ?? 0 }}
                </div>
                <div class="grid-3" style="width: 100%; max-width: 380px; margin-top: 6px">
                  <div class="stat">
                    <span class="stat__num stat__num--plus">{{ summary?.accuracy ?? 0 }}%</span>
                    <span class="stat__label">точность</span>
                  </div>
                  <div class="stat">
                    <span class="stat__num">{{ summary?.avgSeconds ?? 0 }}s</span>
                    <span class="stat__label">среднее</span>
                  </div>
                  <div class="stat">
                    <span class="stat__num stat__num--plus">{{ summary?.score ?? 0 }}</span>
                    <span class="stat__label">очки</span>
                  </div>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 10px">
                  <button class="btn btn--duel" type="button" @click="leavePlay">
                    К лидерборду
                  </button>
                </div>
              </div>
            </template>

            <template v-else-if="current">
              <h1 class="sr-only">
                Турнир {{ tournament.title }} — вопрос {{ questionNumber }} из {{ tasks.length }}
              </h1>
              <div class="run__bar">
                <span class="chip is-on">очки: {{ score }}</span>
                <div class="run__progress"><i :style="{ width: progressPct + '%' }"></i></div>
                <span class="run__count">{{ questionNumber }} / {{ tasks.length }}</span>
              </div>

              <div class="surface qcard" style="margin-top: 8px">
                <div class="qcard__label">Вопрос {{ questionNumber }} · {{ current.body.question }}</div>

                <pre v-if="current.body.code" class="code code--light"><code>{{
                  current.body.code
                }}</code></pre>

                <div class="opts opts--stack" style="margin-top: 14px">
                  <button
                    v-for="(option, i) in current.body.options"
                    :key="i"
                    class="opt opt--light"
                    :class="optClass(i)"
                    type="button"
                    :disabled="optDisabled(i)"
                    @click="session.answer(i)"
                  >
                    {{ option }}
                  </button>
                </div>

                <p
                  v-if="answerError"
                  role="alert"
                  style="color: var(--minus); font-size: 14px; margin-top: 14px"
                >
                  {{ answerError }}
                </p>

                <div v-if="phase === 'verdict' && verdict" class="explain">
                  <div class="explain__tag">// объяснение</div>
                  <p>{{ verdict.explanation }}</p>
                </div>

                <div
                  v-if="phase === 'verdict'"
                  style="display: flex; justify-content: flex-end; margin-top: 16px"
                >
                  <button class="btn btn--duel" type="button" @click="session.next()">
                    Следующий вопрос →
                  </button>
                </div>
              </div>
            </template>
          </div>
        </template>

        <!-- Детали + лидерборд -->
        <template v-else-if="tournament">
          <div class="crumbs" style="padding-top: 14px">
            <RouterLink to="/tournaments">Турниры</RouterLink>
            <span class="crumbs__sep">/</span><b>{{ tournament.title }}</b>
          </div>

          <div class="t-hero">
            <div class="t-hero__in">
              <div>
                <span v-if="status" :class="STATUS_PILL[status]" style="margin-bottom: 8px">
                  <span v-if="status === 'active'" class="live-dot"></span>
                  {{ STATUS_LABEL[status] }}
                </span>
                <h1>{{ tournament.title }}</h1>
                <div class="mono t-sub">
                  {{ tournament.entries_count }} участников · взнос {{ money(tournament.entry_fee) }}
                </div>
              </div>
              <div class="t-hero__prize">
                <b class="t-plus-b">{{ money(tournament.prize_pool) }}</b>
                <span>призовой фонд</span>
              </div>
            </div>
          </div>

          <!-- Действия -->
          <div style="display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap">
            <button
              v-if="!isParticipant && status !== 'finished'"
              class="btn btn--duel"
              type="button"
              :disabled="entering"
              @click="enter"
            >
              {{ entering ? 'Записываем…' : 'Участвовать' }}
            </button>
            <button
              v-if="isParticipant && status === 'active'"
              class="btn btn--duel"
              type="button"
              @click="play"
            >
              Играть
            </button>
            <span v-if="isParticipant && status === 'upcoming'" class="pill pill--soon">
              Вы записаны · ждём старта
            </span>
          </div>
          <p
            v-if="enterMessage"
            role="alert"
            :style="{
              fontSize: '14px',
              marginTop: '12px',
              color: enterIsError ? 'var(--minus)' : 'var(--plus)',
            }"
          >
            {{ enterMessage }}
          </p>

          <!-- Лидерборд -->
          <div class="section" style="margin-top: 18px">
            <div class="surface" style="overflow: hidden">
              <div style="padding: 14px 16px; border-bottom: 1px solid var(--line)">
                <strong style="font: 700 15px var(--font-display); font-stretch: 110%">
                  {{ status === 'finished' ? 'Итоги' : 'Топ участников' }}
                </strong>
              </div>
              <div v-if="tournament.leaderboard.length === 0" style="padding: 24px; color: var(--ink-soft)">
                Пока никто не участвует.
              </div>
              <div v-else style="padding: 4px 12px 8px">
                <div
                  v-for="entry in tournament.leaderboard"
                  :key="entry.user_id"
                  class="lb"
                  :class="{ 'is-me': entry.user_id === myUserId }"
                >
                  <span class="place" :class="entry.place === 1 ? 'place--1' : ''">{{
                    entry.place ?? '—'
                  }}</span>
                  <span class="ava ava--3 ava--sm">{{ entry.username.slice(0, 2).toUpperCase() }}</span>
                  <div class="lb__name">
                    <b>{{ entry.username }}</b>
                    <span>{{ (entry.time_ms / 1000).toFixed(1) }}s</span>
                  </div>
                  <span class="lb__elo diff-plus">{{ entry.score }}</span>
                </div>
              </div>
            </div>
          </div>
          <div style="height: 24px"></div>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.t-hero {
  background: var(--arena);
  color: var(--arena-ink);
  border-radius: var(--radius-lg);
  border: 1px solid var(--frame);
  padding: 26px;
  position: relative;
  overflow: hidden;
  margin-top: 8px;
}
.t-hero::after {
  content: '';
  position: absolute;
  inset: -30% -8% -30% 62%;
  background: linear-gradient(rgb(31 157 85 / 0.2), transparent);
  transform: skewX(var(--split-skew));
  pointer-events: none;
}
.t-hero__in {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 28px;
  align-items: flex-end;
  flex-wrap: wrap;
}
.t-hero h1 {
  font: 800 26px var(--font-display);
  font-stretch: 110%;
}
.t-hero__prize {
  margin-left: auto;
  text-align: right;
}
.t-hero__prize b {
  display: block;
  font: 800 36px var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.t-hero__prize span {
  font: 600 11px var(--font-mono);
  color: var(--arena-soft);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.live-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--timer);
}
.t-sub {
  font-size: 13px;
  color: var(--arena-soft);
  margin-top: 4px;
}
.place {
  font: 800 15px var(--font-mono);
  width: 28px;
  text-align: center;
}
.place--1 {
  color: var(--timer);
}
.run {
  max-width: 680px;
  margin: 0 auto;
  padding: 8px 0 40px;
}
.run__bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 0;
}
.run__progress {
  flex: 1;
  height: 8px;
  border-radius: var(--radius-pill);
  background: var(--seg-bg);
  overflow: hidden;
}
.run__progress > i {
  display: block;
  height: 100%;
  background: var(--plus);
  border-radius: var(--radius-pill);
}
.run__count {
  font: 700 13px var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--ink-soft);
}
.qcard {
  padding: 22px;
}
.qcard__label {
  font: 700 10px var(--font-mono);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-soft);
  margin-bottom: 12px;
}
.explain {
  margin-top: 16px;
  border-top: 1px solid var(--line);
  padding-top: 16px;
}
.explain__tag {
  font: 700 10px var(--font-mono);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--plus);
  margin-bottom: 8px;
}
.explain p {
  font-size: 14px;
  color: var(--ink-soft);
  line-height: 1.6;
}
.summary {
  padding: 24px;
  text-align: center;
  display: grid;
  gap: 8px;
  justify-items: center;
}
</style>
