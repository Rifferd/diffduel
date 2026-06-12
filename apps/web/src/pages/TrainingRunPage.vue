<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { useTrainingSession } from '@/composables/useTrainingSession';

const route = useRoute();

const topic = computed(() => String(route.query.topic ?? ''));
const difficultyParam = computed(() => {
  const raw = Number(route.query.difficulty);
  return Number.isInteger(raw) && raw >= 1 && raw <= 5 ? raw : undefined;
});

const DIFF_LABEL: Record<number, string> = {
  1: 'база',
  2: 'средне',
  3: 'хард',
  4: 'эксперт',
  5: 'гуру',
};
const difficultyLabel = computed(() =>
  difficultyParam.value
    ? (DIFF_LABEL[difficultyParam.value] ?? `ур. ${difficultyParam.value}`)
    : '',
);

/** Подпись чипа/сводки: «SQL · база». */
const chipLabel = computed(() => {
  const t = topic.value.toUpperCase();
  return difficultyLabel.value ? `${t} · ${difficultyLabel.value}` : t;
});

const session = useTrainingSession({
  topic: topic.value,
  difficulty: difficultyParam.value,
});

const {
  phase,
  loadError,
  answerError,
  current,
  verdict,
  selected,
  submitting,
  summary,
  questionNumber,
  tasks,
} = session;

/** Прогресс-бар: ширина в процентах от пройденных вопросов. */
const progressPct = computed(() => {
  const total = tasks.value.length;
  if (total === 0) return 0;
  // В фазе verdict считаем текущий вопрос завершённым.
  const done = phase.value === 'verdict' ? questionNumber.value : questionNumber.value - 1;
  return Math.round((done / total) * 100);
});

/** Класс опции в фазе verdict — по состояниям макета. */
function optClass(optionIndex: number): Record<string, boolean> {
  if (phase.value !== 'verdict' || !verdict.value) return {};
  const isCorrectOption = optionIndex === verdict.value.correct_option;
  const isChosen = optionIndex === selected.value;
  if (verdict.value.correct) {
    // Ответил верно: верная опция подсвечена is-correct, прочие disabled.
    return { 'is-correct': isCorrectOption };
  }
  // Ответил неверно: верная — is-reveal, выбранная — is-wrong.
  return { 'is-reveal': isCorrectOption, 'is-wrong': isChosen && !isCorrectOption };
}

/** Опция кликабельна только в фазе answering. */
function optDisabled(optionIndex: number): boolean {
  if (phase.value === 'answering') return submitting.value;
  // verdict: всё, кроме подсвеченных опций, остаётся disabled (как в макете).
  if (!verdict.value) return true;
  const isCorrectOption = optionIndex === verdict.value.correct_option;
  const isChosen = optionIndex === selected.value;
  return !(isCorrectOption || isChosen);
}

onMounted(() => {
  void session.load();
});
</script>

<template>
  <div class="app">
    <nav class="appnav">
      <div class="wrap appnav__in">
        <RouterLink class="nav__logo" to="/training"><span class="vs">VS</span>DiffDuel</RouterLink>
        <span class="appnav__sp"></span>
        <RouterLink class="appnav__link" to="/training">← Выйти из тренировки</RouterLink>
      </div>
    </nav>

    <main class="app__main">
      <div class="wrap run">
        <!-- Загрузка -->
        <div v-if="phase === 'loading'" class="surface qcard" style="margin-top: 8px">
          <div class="qcard__label">Загружаем задачи…</div>
        </div>

        <!-- Ошибка загрузки -->
        <div v-else-if="phase === 'error'" class="surface qcard" style="margin-top: 8px">
          <div class="qcard__label">Ошибка</div>
          <p style="color: var(--ink-soft); font-size: 14px">{{ loadError }}</p>
          <div style="display: flex; justify-content: flex-end; margin-top: 16px">
            <button class="btn btn--duel" type="button" @click="session.load()">Повторить</button>
          </div>
        </div>

        <!-- Сводка сессии -->
        <template v-else-if="phase === 'summary'">
          <div class="surface summary" style="margin-top: 8px">
            <span class="eyebrow eyebrow--accent"
              >{{ chipLabel }} · {{ tasks.length }} вопросов</span
            >
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
                <span class="stat__num stat__num--plus">{{ chipLabel }}</span>
                <span class="stat__label">тема</span>
              </div>
            </div>
            <div style="display: flex; gap: 10px; margin-top: 10px">
              <button class="btn btn--duel" type="button" @click="session.load()">Ещё 10</button>
              <RouterLink class="btn btn--ghost" to="/training">К темам</RouterLink>
            </div>
          </div>
          <div style="height: 24px"></div>
        </template>

        <!-- Вопрос: answering / verdict -->
        <template v-else-if="current">
          <h1 class="sr-only">
            Тренировка {{ topic }} — вопрос {{ questionNumber }} из {{ tasks.length }}
          </h1>
          <div class="run__bar">
            <span class="chip is-on">{{ chipLabel }}</span>
            <div class="run__progress"><i :style="{ width: progressPct + '%' }"></i></div>
            <span class="run__count">{{ questionNumber }} / {{ tasks.length }}</span>
          </div>

          <div class="surface qcard" style="margin-top: 8px">
            <div class="qcard__label">
              Вопрос {{ questionNumber }} · {{ current.body.question }}
            </div>

            <pre
              v-if="current.body.code"
              class="code code--light"
            ><code>{{ current.body.code }}</code></pre>

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
          <div style="height: 24px"></div>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
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
.explain :deep(code) {
  font-family: var(--font-mono);
  background: var(--row-alt);
  padding: 1px 5px;
  border-radius: 4px;
}
.summary {
  padding: 24px;
  text-align: center;
  display: grid;
  gap: 8px;
  justify-items: center;
}
</style>
