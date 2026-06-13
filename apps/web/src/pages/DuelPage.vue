<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useDuelResultStore } from '@/stores/duelResult';
import { createDuelSocket } from '@/shared/realtime/duelSocket';
import { useDuel, formatClock } from '@/composables/useDuel';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const resultStore = useDuelResultStore();

const topicParam = computed(() => String(route.query.topic ?? ''));

const socket = createDuelSocket({ getToken: () => auth.accessToken });
const duel = useDuel({
  socket,
  myUserId: auth.user?.id ?? null,
  myUsername: auth.user?.username,
});

const {
  phase,
  topic,
  opponent,
  tasksCount,
  taskIndex,
  taskBody,
  secondsLeft,
  roundProgress,
  myScore,
  oppScore,
  opponentStatus,
  verdict,
  selected,
  answered,
  result,
  errorMessage,
  reducedMotion,
} = duel;

const myUsername = computed(() => auth.user?.username ?? 'вы');
const myInitials = computed(() => myUsername.value.slice(0, 2).toUpperCase());
const oppName = computed(() => opponent.value?.username ?? 'соперник');
const oppInitials = computed(() => oppName.value.slice(0, 2).toUpperCase());

const taskNumber = computed(() => (taskIndex.value ?? 0) + 1);
const totalTasks = computed(() => tasksCount.value || 5);
const clock = computed(() => formatClock(secondsLeft.value));
const tbarWidth = computed(() => `${Math.round((1 - roundProgress.value) * 100)}%`);
const topicLabel = computed(() => (topic.value || topicParam.value || 'код').toUpperCase());

const timerClass = computed(() => ({
  'duel-timer--urgent': secondsLeft.value <= 5 && secondsLeft.value > 0 && !answered.value,
  'duel-timer--expired': secondsLeft.value <= 0,
}));

/** Подсветка опции после моего вердикта (см. duel.html demo-states). */
function optClass(i: number): Record<string, boolean> {
  if (!verdict.value) {
    return { 'is-selected': selected.value === i };
  }
  const isCorrectOption = i === verdict.value.correctOption;
  const isChosen = i === selected.value;
  if (verdict.value.correct) return { 'is-correct': isCorrectOption };
  return { 'is-reveal': isCorrectOption, 'is-wrong': isChosen && !isCorrectOption };
}

function optDisabled(i: number): boolean {
  // До ответа — все доступны; после — заблокированы.
  if (!answered.value && phase.value === 'playing') return false;
  void i;
  return true;
}

/** Лента событий внизу экрана. */
const feedText = computed(() => {
  if (opponentStatus.value.answered && opponentStatus.value.timeMs !== null) {
    const t = (opponentStatus.value.timeMs / 1000).toFixed(1);
    const lead =
      myScore.value > oppScore.value
        ? `вы впереди ${myScore.value}:${oppScore.value}`
        : myScore.value < oppScore.value
          ? `соперник впереди ${oppScore.value}:${myScore.value}`
          : `счёт ${myScore.value}:${oppScore.value}`;
    return { name: oppName.value, time: `${t}s`, lead, leadPlus: myScore.value >= oppScore.value };
  }
  return null;
});

watch(
  () => phase.value,
  (p) => {
    if (p === 'finished' && result.value) {
      resultStore.set(result.value);
      void router.replace({ path: '/duel/result' });
    }
  },
);

onBeforeUnmount(() => {
  socket.disconnect();
});

function surrender(): void {
  duel.leaveQueue();
  socket.disconnect();
  void router.push('/');
}
</script>

<template>
  <main class="arena duel-arena">
    <h1 class="sr-only">
      Дуэль: {{ myUsername }} против {{ oppName }} — задача {{ taskNumber }} из {{ totalTasks }}
    </h1>

    <div class="arena__bar">
      <RouterLink class="arena__logo" to="/"><span class="vs">VS</span>DiffDuel</RouterLink>
      <button class="arena__exit" type="button" @click="surrender">
        <svg viewBox="0 0 24 24">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
        </svg>
        Сдаться
      </button>
    </div>

    <div class="arena__head">
      <div class="duel-head">
        <div class="duel-head__player">
          <span class="ava ava--you ava--md">{{ myInitials }}</span>
          <div>
            <div class="duel-head__nm duel-head__nm--you">{{ myUsername }}</div>
            <div class="duel-head__score">{{ myScore }}</div>
          </div>
        </div>
        <span class="duel-head__vs">VS</span>
        <div class="duel-head__player duel-head__player--right">
          <div>
            <div class="duel-head__nm duel-head__nm--rival">{{ oppName }}</div>
            <div class="duel-head__score">{{ oppScore }}</div>
          </div>
          <span class="ava ava--rival ava--md">{{ oppInitials }}</span>
        </div>
      </div>
    </div>

    <!-- Баннер переподключения -->
    <div v-if="phase === 'reconnecting'" class="arena__timer">
      <div class="banner banner--warn">
        <span class="banner__mark">!</span> Восстанавливаем дуэль… таймер приостановлен
      </div>
    </div>

    <!-- Системная ошибка -->
    <div v-else-if="phase === 'error'" class="arena__timer">
      <div class="banner banner--error">
        <span class="banner__mark">!</span> {{ errorMessage }}
      </div>
    </div>

    <div v-else class="arena__timer">
      <div
        class="duel-timer"
        :class="[timerClass, { 'duel-timer--paused': reducedMotion }]"
      >
        <span class="duel-timer__num" role="timer" :aria-label="`Осталось ${secondsLeft} секунд`">{{
          clock
        }}</span>
        <div class="tbar"><i :style="{ width: tbarWidth }"></i></div>
        <span class="duel-timer__step">{{ taskNumber }}/{{ totalTasks }}</span>
      </div>
    </div>

    <div class="arena__task">
      <template v-if="taskBody">
        <div class="task-label">{{ topicLabel }} · задача {{ taskNumber }}</div>
        <p class="duel-q">{{ taskBody.question }}</p>
        <pre v-if="taskBody.code" class="code"><code>{{ taskBody.code }}</code></pre>

        <div class="opts" role="radiogroup" aria-label="Варианты ответа">
          <button
            v-for="(opt, i) in taskBody.options"
            :key="i"
            class="opt"
            :class="optClass(i)"
            type="button"
            role="radio"
            :aria-checked="selected === i"
            :disabled="optDisabled(i)"
            @click="duel.answer(i)"
          >
            {{ opt }}
          </button>
        </div>

        <div v-if="answered && !opponentStatus.answered && phase === 'playing'" class="wait">
          <span class="wait__dot"></span> ждём ответ соперника…
        </div>
      </template>

      <div v-else class="task-label">Готовим задачу…</div>
    </div>

    <div class="arena__feed">
      <div v-if="feedText" class="feed" aria-live="polite">
        › {{ feedText.name }} ответил за <b class="m">{{ feedText.time }}</b> ·
        <b :class="feedText.leadPlus ? 'p' : 'm'">{{ feedText.lead }}</b>
      </div>
    </div>
  </main>
</template>

<style scoped>
.arena {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  max-width: 720px;
  margin: 0 auto;
  background: var(--arena);
  color: var(--arena-ink);
}
.arena__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
}
.arena__logo {
  font: 800 16px var(--font-display);
  font-stretch: 110%;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--arena-ink);
  text-decoration: none;
}
.arena__exit {
  color: var(--arena-soft);
  text-decoration: none;
  font: 600 13px var(--font-body);
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: 0;
  cursor: pointer;
}
.arena__exit svg {
  width: 16px;
  height: 16px;
  stroke: currentColor;
  fill: none;
  stroke-width: 2;
}
.arena__head {
  padding: 0 18px;
}
.arena__head .duel-head {
  border-radius: var(--radius-lg);
  border: 1px solid var(--arena-line);
}
.arena__head .duel-head__score {
  font-size: 24px;
}
.arena__timer {
  padding: 4px 18px 0;
}
.arena__task {
  flex: 1;
  padding: 12px 18px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.arena__task .task-label {
  font: 700 10px var(--font-mono);
  letter-spacing: 0.12em;
  color: var(--arena-soft);
  text-transform: uppercase;
  margin-bottom: 10px;
}
.duel-q {
  font: 600 16px var(--font-body);
  margin-bottom: 14px;
}
.arena__task pre.code {
  margin-bottom: 14px;
  max-height: 38vh;
}
.arena__feed {
  padding: 0 18px;
}
.arena__feed .feed {
  padding: 12px 0 max(16px, env(safe-area-inset-bottom));
}
.wait {
  display: flex;
  align-items: center;
  gap: 8px;
  font: 500 12px var(--font-mono);
  color: var(--arena-soft);
  padding: 6px 0;
}
.wait__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--arena-soft);
  animation: dd-blink 1s infinite;
}
@keyframes dd-blink {
  50% {
    opacity: 0.3;
  }
}
@media (prefers-reduced-motion: reduce) {
  .wait__dot {
    animation: none;
  }
}
@media (max-width: 640px) {
  .arena__head .duel-head {
    border: 0;
    border-radius: 0;
    padding: 8px 0;
    background:
      linear-gradient(var(--split-angle), rgb(31 157 85 / 0.16) 49.6%, transparent 49.6%),
      linear-gradient(282deg, rgb(229 72 77 / 0.16) 49.6%, transparent 49.6%);
  }
  .arena__head {
    padding: 0 14px;
  }
  .arena__timer,
  .arena__task,
  .arena__feed {
    padding-left: 14px;
    padding-right: 14px;
  }
}
</style>
