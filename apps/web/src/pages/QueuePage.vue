<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { createDuelSocket } from '@/shared/realtime/duelSocket';
import { useDuel } from '@/composables/useDuel';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const topic = computed(() => String(route.query.topic ?? 'sql'));

const socket = createDuelSocket({ getToken: () => auth.accessToken });
const duel = useDuel({
  socket,
  myUserId: auth.user?.id ?? null,
  myUsername: auth.user?.username,
});

const { phase, opponent, countdown } = duel;

/** Шаг расширения окна поиска — обновляется из queue.searching. */
const widening = ref(0);
socket.on('queue.searching', (e) => {
  widening.value = e.widening;
});

const myUsername = computed(() => auth.user?.username ?? 'вы');
const myInitials = computed(() => myUsername.value.slice(0, 2).toUpperCase());
const oppInitials = computed(() => (opponent.value?.username ?? '?').slice(0, 2).toUpperCase());

function formatElo(elo: number | null | undefined): string {
  if (typeof elo !== 'number') return '—';
  return elo.toLocaleString('ru-RU').replace(/,/g, ' ');
}

/** Шкала расширения окна для индикатора (±150 → ±300 → ±500). */
const STEPS = [150, 300, 500];
function stepActive(i: number): boolean {
  return widening.value >= i;
}

const isFound = computed(() => phase.value === 'matched' || phase.value === 'countdown');

function cancel(): void {
  duel.leaveQueue();
  void router.push('/');
}

// Когда пришёл первый duel.task — дуэль началась, уходим на боевой экран,
// передавая управление тем же сокетом через sessionStorage-флаг недостаточно;
// /duel создаёт собственный сокет и получит system.reconnect_state. Здесь
// достаточно перейти по началу countdown→playing.
watch(phase, (p) => {
  if (p === 'playing') {
    void router.replace({ path: '/duel', query: { topic: topic.value } });
  }
});

onMounted(() => {
  duel.joinQueue(topic.value);
});

onBeforeUnmount(() => {
  // Уходим со страницы: если ещё ищем — снять с очереди.
  if (phase.value === 'searching') duel.leaveQueue();
  socket.disconnect();
});
</script>

<template>
  <body class="arena-screen">
    <h1 class="sr-only">Поиск соперника для дуэли по {{ topic.toUpperCase() }}</h1>
    <div class="arena-screen__bar">
      <RouterLink class="arena-screen__logo" to="/"><span class="vs">VS</span>DiffDuel</RouterLink>
      <span class="eyebrow eyebrow--arena">// {{ topic.toUpperCase() }} · рейтинговая</span>
    </div>

    <main class="arena-screen__body arena-screen__body--start">
      <div class="q">
        <!-- searching -->
        <div v-if="!isFound" class="q__state">
          <span class="q__label">// состояние: поиск</span>
          <div class="radar">
            <span class="radar__ring"></span>
            <span class="radar__ring"></span>
            <span class="radar__ring"></span>
            <span class="radar__vs">VS</span>
          </div>
          <div class="q__title">Ищем соперника</div>
          <div class="q__window">
            <template v-for="(s, i) in STEPS" :key="s">
              <span class="step" :class="{ 'is-on': stepActive(i) }">±{{ s }}</span>
              <span v-if="i < STEPS.length - 1">→</span>
            </template>
          </div>
          <p class="q__hint" style="max-width: 38ch">
            Подбираем игрока вашего уровня. Каждые 5 секунд расширяем окно поиска.
          </p>
          <button class="btn btn--dark-ghost" type="button" @click="cancel">Отменить</button>
        </div>

        <!-- found / countdown -->
        <div v-else class="q__state">
          <span class="q__label">// состояние: соперник найден</span>
          <div class="q__found">
            <div class="q__pl q__pl--you">
              <span class="ava ava--you">{{ myInitials }}</span>
              <b>{{ myUsername }}</b><span>рейтинг</span>
            </div>
            <span class="q__vs-lg">VS</span>
            <div class="q__pl q__pl--rival">
              <span class="ava ava--rival">{{ oppInitials }}</span>
              <b>{{ opponent?.username ?? 'соперник' }}</b
              ><span>{{ formatElo(opponent?.elo) }}</span>
            </div>
          </div>
          <div
            v-if="countdown !== null"
            class="q__count"
            role="timer"
            :aria-label="`Дуэль начнётся через ${countdown} секунд`"
          >
            {{ countdown }}
          </div>
          <div class="q__title">Соперник найден</div>
          <p class="q__hint">Дуэль начнётся через несколько секунд…</p>
        </div>
      </div>
    </main>
  </body>
</template>

<style scoped>
.q {
  max-width: 560px;
  margin: 0 auto;
  width: 100%;
  padding: 8px 18px 40px;
  display: grid;
  gap: 24px;
}
.q__state {
  display: grid;
  gap: 18px;
  justify-items: center;
  text-align: center;
  padding: 24px 0;
}
.q__label {
  font: 700 10px var(--font-mono);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--arena-soft);
}
.q__title {
  font: 800 24px var(--font-display);
  font-stretch: 110%;
}
.q__window {
  display: flex;
  align-items: center;
  gap: 10px;
  font: 600 12px var(--font-mono);
  color: var(--arena-soft);
}
.q__window .step {
  padding: 3px 9px;
  border: 1px solid var(--arena-line);
  border-radius: var(--radius-pill);
}
.q__window .step.is-on {
  border-color: var(--plus);
  color: var(--plus-bright);
}
.q__found {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 14px;
  width: 100%;
  background: linear-gradient(
    var(--split-angle),
    rgb(31 157 85 / 0.16) 49.6%,
    rgb(229 72 77 / 0.16) 50.4%
  );
  border: 1px solid var(--arena-line);
  border-radius: var(--radius-lg);
  padding: 22px 18px;
}
.q__pl {
  display: grid;
  gap: 8px;
  justify-items: center;
}
.q__pl .ava {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  font-size: 16px;
}
.q__pl b {
  font-size: 14px;
}
.q__pl span {
  font: 500 11px var(--font-mono);
  color: var(--arena-soft);
}
.q__pl--you b {
  color: var(--plus-bright);
}
.q__pl--rival b {
  color: var(--minus-bright);
}
.q__vs-lg {
  font: 800 22px var(--font-display);
  color: var(--arena-ink);
}
.q__count {
  font: 800 56px var(--font-mono);
  color: var(--plus-bright);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.arena-screen__body--start {
  display: block;
  align-content: start;
}
.q__hint {
  color: var(--arena-soft);
  font-size: 13px;
  margin: 0 auto;
}
</style>
