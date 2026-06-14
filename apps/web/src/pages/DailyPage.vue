<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useDailyChallenge } from '@/composables/useDailyChallenge';
import AppNav from '@/components/AppNav.vue';
import TabBar from '@/components/TabBar.vue';

const auth = useAuthStore();
const myUserId = computed(() => auth.user?.id ?? null);

const daily = useDailyChallenge();
const {
  phase,
  loadError,
  answerError,
  challengeDate,
  task,
  selected,
  submitting,
  result,
  leaderboard,
  myPosition,
} = daily;

const dateLabel = computed(() => {
  if (!challengeDate.value) return '';
  return new Date(challengeDate.value).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
  });
});

const topicLabel = computed(() => {
  const tags = task.value?.body.tags;
  return tags && tags.length ? tags[0].toUpperCase() : 'код';
});

/** Класс опции в фазе результата — по состояниям макета. */
function optClass(i: number): Record<string, boolean> {
  if (phase.value !== 'result' || !result.value) {
    return { 'is-selected': selected.value === i };
  }
  const isCorrectOption = i === result.value.correct_option;
  const isChosen = i === selected.value;
  if (result.value.correct) return { 'is-correct': isCorrectOption };
  return { 'is-reveal': isCorrectOption, 'is-wrong': isChosen && !isCorrectOption };
}

function optDisabled(i: number): boolean {
  if (phase.value === 'answering') return submitting.value;
  if (!result.value) return true;
  const isCorrectOption = i === result.value.correct_option;
  const isChosen = i === selected.value;
  return !(isCorrectOption || isChosen);
}

const AVA_CLASSES = ['ava--3', 'ava--rival', 'ava--4', 'ava--2'];
function avaClass(i: number): string {
  return AVA_CLASSES[i % AVA_CLASSES.length];
}
function initials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

onMounted(() => {
  void daily.load();
});
</script>

<template>
  <div class="app">
    <AppNav active="daily" />

    <main class="app__main">
      <div class="wrap">
        <div class="page-head">
          <span class="eyebrow">// одна задача · одна попытка · общий рейтинг</span>
          <h1>Задача дня<span v-if="dateLabel"> · {{ dateLabel }}</span></h1>
        </div>

        <div class="section daily-grid">
          <!-- Загрузка -->
          <div v-if="phase === 'loading'" class="surface qcard">
            <div class="qcard__label">Загружаем задачу дня…</div>
          </div>

          <!-- Ошибка -->
          <div v-else-if="phase === 'error'" class="surface qcard">
            <div class="qcard__label">Ошибка</div>
            <p style="color: var(--ink-soft); font-size: 14px">{{ loadError }}</p>
            <div style="display: flex; justify-content: flex-end; margin-top: 16px">
              <button class="btn btn--duel" type="button" @click="daily.load()">Повторить</button>
            </div>
          </div>

          <!-- Задача: answering / result -->
          <div v-else-if="task" class="surface qcard">
            <div class="qcard__label">{{ dateLabel }} · {{ topicLabel }}</div>
            <p style="font: 600 15px var(--font-body); margin-bottom: 4px">
              {{ task.body.question }}
            </p>
            <pre v-if="task.body.code" class="code"><code>{{ task.body.code }}</code></pre>

            <div class="opts opts--stack" style="margin-top: 14px">
              <button
                v-for="(option, i) in task.body.options"
                :key="i"
                class="opt"
                :class="optClass(i)"
                type="button"
                :disabled="optDisabled(i)"
                @click="daily.answer(i)"
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

            <template v-if="phase === 'result' && result">
              <div class="explain">
                <div
                  class="explain__tag"
                  :style="{ color: result.correct ? 'var(--plus)' : 'var(--minus)' }"
                >
                  {{ result.correct ? '// верно' : '// неверно' }}
                </div>
                <p>{{ result.explanation }}</p>
              </div>
              <p
                v-if="result.already_answered"
                class="t-soft"
                style="font-size: 13px; margin-top: 10px"
                data-test="already"
              >
                Зачётный ответ на сегодня уже был — этот в рейтинг не пойдёт.
              </p>
              <p
                v-else-if="result.scored"
                class="t-soft"
                style="font-size: 13px; margin-top: 10px"
                data-test="scored"
              >
                Ответ засчитан в рейтинг дня.
              </p>
            </template>

            <div
              v-else-if="phase === 'answering'"
              style="display: flex; justify-content: flex-end; margin-top: 16px"
            >
              <span class="t-soft" style="font-size: 12px">Одна попытка засчитывается в рейтинг.</span>
            </div>
          </div>

          <!-- Боковая колонка: лидерборд дня + моя позиция -->
          <div style="display: grid; gap: 14px">
            <div v-if="myPosition && myPosition.rank !== null" class="surface cd-card" data-test="my-pos">
              <span class="eyebrow">// моя позиция</span>
              <div class="cd cd--lg"><span class="cd__num">#{{ myPosition.rank }}</span></div>
              <span class="t-soft" style="font-size: 12px">{{ myPosition.score }} очков</span>
            </div>

            <div class="surface pad">
              <div class="section__head" style="margin: 0 0 10px">
                <h2 style="font-size: 15px">Топ дня</h2>
              </div>
              <p v-if="leaderboard.length === 0" class="t-soft" style="font-size: 13px">
                Пока никто не решил — будьте первым.
              </p>
              <div
                v-for="(entry, i) in leaderboard"
                :key="entry.user_id"
                class="lb"
                :class="{ 'lb--me': entry.user_id === myUserId }"
              >
                <span class="lb__pos">{{ entry.rank }}</span>
                <span class="ava ava--sm" :class="avaClass(i)">{{ initials(entry.username) }}</span>
                <div class="lb__name">
                  <b>{{ entry.username }}</b><span>{{ entry.score }}</span>
                </div>
                <span class="lb__elo diff-plus">✓</span>
              </div>
            </div>
          </div>
        </div>
        <div style="height: 24px"></div>
      </div>
    </main>

    <TabBar active="daily" />
  </div>
</template>

<style scoped>
.daily-grid {
  display: grid;
  grid-template-columns: 1.4fr 0.8fr;
  gap: 16px;
  align-items: start;
}
@media (max-width: 640px) {
  .daily-grid {
    grid-template-columns: 1fr;
  }
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
.cd-card {
  padding: 20px;
  text-align: center;
  display: grid;
  gap: 6px;
  justify-items: center;
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
  margin-bottom: 8px;
}
.explain p {
  font-size: 14px;
  color: var(--ink-soft);
  line-height: 1.6;
}
.lb--me {
  background: var(--row-alt);
  border-radius: 8px;
}
</style>
