<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useDuelResultStore } from '@/stores/duelResult';

const router = useRouter();
const auth = useAuthStore();
const resultStore = useDuelResultStore();

const result = computed(() => resultStore.result);

// Зашли без данных (перезагрузка) — редирект на главную.
onMounted(() => {
  if (!result.value) void router.replace('/');
});

const myUsername = computed(() => auth.user?.username ?? 'вы');
const oppName = computed(() => result.value?.opponent?.username ?? 'соперник');
const topicLabel = computed(() => (result.value?.topic || 'код').toUpperCase());

const outcome = computed(() => result.value?.outcome ?? 'draw');
const titleText = computed(
  () => ({ win: 'ПОБЕДА', loss: 'ПОРАЖЕНИЕ', draw: 'НИЧЬЯ' })[outcome.value],
);
const titleClass = computed(
  () =>
    ({ win: 'res-head__title--win', loss: 'res-head__title--loss', draw: 'res-head__title--draw' })[
      outcome.value
    ],
);

const myUserId = computed(() => auth.user?.id ?? null);

/** Дельта Эло по моему user_id. */
const myDelta = computed<number>(() => {
  const r = result.value;
  if (!r || myUserId.value === null) return 0;
  return r.deltas[myUserId.value] ?? 0;
});
const myElo = computed<number | null>(() => {
  const r = result.value;
  if (!r || myUserId.value === null) return null;
  return r.elo[myUserId.value] ?? null;
});

/** Дельта соперника — берём оставшийся ключ в deltas. */
const oppDelta = computed<number | null>(() => {
  const r = result.value;
  if (!r) return null;
  const keys = Object.keys(r.deltas).filter((k) => k !== myUserId.value);
  return keys.length ? (r.deltas[keys[0]] ?? null) : null;
});

function fmtDelta(d: number): string {
  if (d > 0) return `+${d} Elo`;
  if (d < 0) return `−${Math.abs(d)} Elo`;
  return '0 Elo';
}

/** Diff-строка дельты с целевым Эло (для заголовка). */
const deltaLine = computed(() => {
  const d = myDelta.value;
  const elo = myElo.value;
  const sign = d > 0 ? `+${d}` : d < 0 ? `−${Math.abs(d)}` : '0';
  const target = elo !== null ? ` → ${formatElo(elo)}` : '';
  return `${sign} Elo${target}`;
});
const deltaClass = computed(() =>
  myDelta.value > 0 ? 'diff-plus' : myDelta.value < 0 ? 'diff-minus' : 'diff--zero',
);
const shareDeltaClass = computed(() => (myDelta.value >= 0 ? 'share__d--plus' : 'share__d--minus'));
const shareOppDeltaClass = computed(() =>
  (oppDelta.value ?? 0) >= 0 ? 'share__d--plus' : 'share__d--minus',
);

function formatElo(elo: number): string {
  return elo.toLocaleString('ru-RU').replace(/,/g, ' ');
}

function fmtShareDelta(d: number | null): string {
  if (d === null) return '';
  return d > 0 ? `+${d}` : d < 0 ? `−${Math.abs(d)}` : '0';
}

const shareClass = computed(
  () => ({ win: '', loss: 'share--loss', draw: 'share--draw' })[outcome.value],
);

function goHome(): void {
  resultStore.clear();
  void router.push('/');
}
</script>

<template>
  <main v-if="result" class="wrap res">
    <div class="res__grid">
      <!-- left: outcome -->
      <div>
        <div class="res-head">
          <span class="eyebrow">// дуэль завершена</span>
          <h1 class="res-head__title" :class="titleClass">{{ titleText }}</h1>
          <div class="res-head__delta" :class="deltaClass">{{ deltaLine }}</div>
        </div>
        <div class="share" :class="shareClass" style="margin: 14px 0">
          <div class="share__top"><span>DIFFDUEL</span><span>{{ topicLabel }}</span></div>
          <div class="share__score">
            <div>
              <div class="share__s">{{ result.score.mine }}</div>
              <div class="share__n">{{ myUsername }}</div>
              <div class="share__d" :class="shareDeltaClass">{{ fmtShareDelta(myDelta) }}</div>
            </div>
            <div class="share__colon">:</div>
            <div>
              <div class="share__s">{{ result.score.opp }}</div>
              <div class="share__n">{{ oppName }}</div>
              <div class="share__d" :class="shareOppDeltaClass">{{ fmtShareDelta(oppDelta) }}</div>
            </div>
          </div>
          <div class="share__bottom"><span>{{ fmtDelta(myDelta) }}</span><span>diffduel.com</span></div>
        </div>
        <div class="btn-row">
          <button class="btn btn--duel" type="button" disabled title="Скоро">Реванш</button>
          <button class="btn btn--ghost" type="button" @click="goHome">На главную</button>
        </div>
      </div>

      <!-- right: score summary -->
      <div style="display: grid; gap: 14px">
        <div class="breakdown">
          <div class="breakdown__hd">
            <h3>Итог дуэли</h3><span class="eyebrow">вы · соперник</span>
          </div>
          <div class="br-row" :class="outcome === 'win' ? 'is-win' : outcome === 'loss' ? 'is-lose' : ''">
            <span class="br-row__n">∑</span>
            <span>Счёт</span>
            <span class="br-row__t">{{ result.score.mine }} · {{ result.score.opp }}</span>
            <span
              class="br-row__sign"
              :class="outcome === 'win' ? 'diff-plus' : outcome === 'loss' ? 'diff-minus' : 'diff--zero'"
              >{{ outcome === 'win' ? '+' : outcome === 'loss' ? '−' : '=' }}</span
            >
          </div>
          <div class="br-row">
            <span class="br-row__n">Δ</span>
            <span>Эло</span>
            <span class="br-row__t">{{ fmtShareDelta(myDelta) }} · {{ fmtShareDelta(oppDelta) }}</span>
            <span class="br-row__sign" :class="deltaClass">{{ myDelta >= 0 ? '+' : '−' }}</span>
          </div>
        </div>
        <button class="btn btn--ghost" type="button" disabled title="Скоро">Реванш</button>
      </div>
    </div>
  </main>
</template>

<style scoped>
.res {
  max-width: 960px;
  margin: 0 auto;
  padding: 28px 0 48px;
}
.res__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  align-items: start;
}
.res-head {
  text-align: center;
  padding: 8px 0 6px;
}
.res-head__title {
  font: 800 34px var(--font-display);
  font-stretch: 110%;
}
.res-head__title--win {
  color: var(--plus);
}
.res-head__title--loss {
  color: var(--minus);
}
.res-head__title--draw {
  color: var(--ink-soft);
}
.res-head__delta {
  font: 700 15px var(--font-mono);
  font-variant-numeric: tabular-nums;
  margin-top: 2px;
}
.btn-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 14px;
}
.breakdown {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.breakdown__hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}
.breakdown__hd h3 {
  font: 700 15px var(--font-display);
  font-stretch: 110%;
}
.br-row {
  display: grid;
  grid-template-columns: 24px 1fr auto auto;
  gap: 12px;
  align-items: center;
  padding: 11px 16px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.br-row:last-child {
  border-bottom: 0;
}
.br-row__n {
  font: 700 12px var(--font-mono);
  color: var(--ink-soft);
}
.br-row__t {
  font: 700 12px var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.br-row__sign {
  width: 18px;
  text-align: center;
  font: 700 13px var(--font-mono);
}
.br-row.is-win {
  background: rgb(31 157 85 / 0.05);
}
.br-row.is-lose {
  background: rgb(229 72 77 / 0.05);
}
@media (max-width: 640px) {
  .res__grid {
    grid-template-columns: 1fr;
  }
  .res {
    padding: 20px 0 40px;
  }
}
</style>
