<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { useAiReview } from '@/composables/useAiReview';
import Paywall from '@/components/Paywall.vue';

const route = useRoute();
const duelId = computed(() => String(route.params.duelId ?? ''));

const review = useAiReview({ duelId: duelId.value });
const { phase, content, errorText } = review;

/** Markdown→текст: режем на абзацы по пустой строке, чтобы читалось без рендерера. */
const paragraphs = computed(() =>
  (content.value ?? '')
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0),
);

onMounted(() => {
  void review.start();
});
</script>

<template>
  <div class="app">
    <nav class="appnav">
      <div class="wrap appnav__in">
        <RouterLink class="nav__logo" to="/app"><span class="vs">VS</span>DiffDuel</RouterLink>
        <span class="appnav__sp"></span>
        <RouterLink class="appnav__link" to="/app">← К дуэлям</RouterLink>
      </div>
    </nav>

    <main class="app__main">
      <div class="wrap rev">
        <div class="rev-head">
          <div>
            <span class="eyebrow eyebrow--accent">// AI-разбор · Pro</span>
            <h1 style="font: 800 26px var(--font-display); font-stretch: 110%">Разбор дуэли</h1>
          </div>
        </div>

        <!-- Пейволл (402 pro_required) -->
        <Paywall
          v-if="phase === 'paywall'"
          title="AI-разбор — функция Pro"
          text="Оформите Pro, чтобы получать подробный разбор ошибок дуэли с советами по каждой проваленной задаче."
        />

        <!-- Идёт генерация -->
        <div v-else-if="phase === 'pending'" class="surface rev-card" data-test="pending">
          <div class="qcard__label">// AI анализирует дуэль…</div>
          <p>Это занимает несколько секунд. Можно не закрывать страницу — разбор появится сам.</p>
        </div>

        <!-- Готово -->
        <div v-else-if="phase === 'done'" class="surface rev-card" data-test="done">
          <p v-for="(p, i) in paragraphs" :key="i">{{ p }}</p>
          <p v-if="paragraphs.length === 0" class="t-soft">Разбор пуст.</p>
        </div>

        <!-- Ошибка генерации / сети -->
        <div
          v-else-if="phase === 'failed' || phase === 'error'"
          class="surface rev-card"
          data-test="failed"
        >
          <div class="qcard__label" style="color: var(--minus)">// разбор не удался</div>
          <p>{{ errorText }}</p>
          <div style="display: flex; justify-content: flex-end; margin-top: 8px">
            <button class="btn btn--duel" type="button" @click="review.start()">Повторить</button>
          </div>
        </div>

        <div class="surface pad-lg rev-foot">
          <div style="flex: 1">
            <strong style="font: 700 15px var(--font-display); font-stretch: 110%"
              >Закрепите слабые темы</strong
            >
            <div class="t-soft" style="font-size: 13px">Тренируйтесь, чтобы поднять Эло.</div>
          </div>
          <RouterLink class="btn btn--duel" to="/training">К тренировке</RouterLink>
        </div>
        <div style="height: 24px"></div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.rev {
  max-width: 640px;
  margin: 0 auto;
  padding: 8px 0 40px;
  display: grid;
  gap: 16px;
}
.rev-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  padding: 16px 0 4px;
}
.rev-card {
  padding: 22px;
  display: grid;
  gap: 14px;
}
.rev-card p {
  font-size: 14px;
  color: var(--ink-soft);
  line-height: 1.6;
  white-space: pre-wrap;
}
.qcard__label {
  font: 700 10px var(--font-mono);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-soft);
}
.rev-foot {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
</style>
