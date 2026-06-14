<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import type { UserStats } from '@diffduel/contracts';
import { useAuthStore } from '@/stores/auth';
import { meApi } from '@/shared/api/endpoints';
import { ApiRequestError } from '@/shared/api/client';
import { isProRequired } from '@/shared/api/errors';
import AppNav from '@/components/AppNav.vue';
import TabBar from '@/components/TabBar.vue';
import Paywall from '@/components/Paywall.vue';

const auth = useAuthStore();

const user = computed(() => auth.user);
const isPro = computed(() => user.value?.is_pro === true);
const initials = computed(() => (user.value?.username ?? '').slice(0, 2).toUpperCase());
const memberSince = computed(() => {
  if (!user.value) return '';
  const d = new Date(user.value.created_at);
  return d.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
});

const newName = ref('');
watch(
  user,
  (u) => {
    if (u) newName.value = u.username;
  },
  { immediate: true },
);

const editing = ref(false);
const saving = ref(false);
const error = ref<string | null>(null);
const okMsg = ref<string | null>(null);

function startEdit(): void {
  error.value = null;
  okMsg.value = null;
  editing.value = true;
}

async function save(): Promise<void> {
  error.value = null;
  okMsg.value = null;
  const name = newName.value.trim();
  if (name.length < 3) {
    error.value = 'Минимум 3 символа.';
    return;
  }
  if (name === user.value?.username) {
    editing.value = false;
    return;
  }
  saving.value = true;
  try {
    const updated = await meApi.update({ username: name });
    auth.user = updated;
    editing.value = false;
    okMsg.value = 'Ник обновлён.';
  } catch (err) {
    if (err instanceof ApiRequestError) {
      error.value = err.status === 409 ? 'Этот ник уже занят.' : err.message;
    } else {
      error.value = 'Не удалось сохранить. Попробуйте позже.';
    }
  } finally {
    saving.value = false;
  }
}

// --- Расширенная статистика (Pro-функция, 402 pro_required без Pro) ---
type StatsPhase = 'loading' | 'ready' | 'paywall' | 'error';
const statsPhase = ref<StatsPhase>('loading');
const stats = ref<UserStats | null>(null);
const STATS_PERIOD = 90;

async function loadStats(): Promise<void> {
  statsPhase.value = 'loading';
  try {
    stats.value = await meApi.stats(STATS_PERIOD);
    statsPhase.value = 'ready';
  } catch (err) {
    if (isProRequired(err)) {
      statsPhase.value = 'paywall';
      return;
    }
    statsPhase.value = 'error';
  }
}

onMounted(() => {
  void loadStats();
});
</script>

<template>
  <div class="app">
    <AppNav active="profile" />

    <main class="app__main">
      <div class="wrap">
        <div class="phead">
          <span class="ava ava--you phead__ava">{{ initials }}</span>
          <div>
            <h1 v-if="!editing" class="phead__name">
              {{ user?.username }}
              <span v-if="isPro" class="pill pill--pro" data-test="pro-badge">PRO</span>
              <button
                class="btn btn--ghost"
                type="button"
                style="padding: 4px 10px; font-size: 12px"
                @click="startEdit"
              >
                Переименовать
              </button>
            </h1>
            <div v-else class="phead__name" style="gap: 8px">
              <input v-model="newName" class="field" type="text" style="width: 220px" />
              <button class="btn btn--duel" type="button" :disabled="saving" @click="save">
                {{ saving ? '…' : 'Сохранить' }}
              </button>
              <button
                class="btn btn--ghost"
                type="button"
                :disabled="saving"
                @click="editing = false"
              >
                Отмена
              </button>
            </div>
            <div class="phead__sub">{{ memberSince ? `с ${memberSince}` : '' }}</div>
            <p v-if="error" class="field__hint" role="alert" style="color: var(--minus)">
              {{ error }}
            </p>
            <p
              v-if="okMsg"
              class="field__hint field__hint--ok"
              style="color: var(--plus)"
              data-test="ok"
            >
              {{ okMsg }}
            </p>
          </div>
          <div class="phead__elo"><b>—</b><span>Elo</span></div>
        </div>

        <div class="section">
          <div class="section__head" style="margin: 0 0 12px">
            <h2 style="font-size: 16px">Расширенная статистика · {{ STATS_PERIOD }} дней</h2>
          </div>

          <!-- Пейволл: не-Pro -->
          <Paywall
            v-if="statsPhase === 'paywall'"
            title="Расширенная статистика — Pro"
            text="Pro открывает точность по темам за 90 дней — видно, какие темы тянут Эло вниз."
          />

          <div v-else-if="statsPhase === 'loading'" class="surface pad-lg">
            <div class="empty__text">Загружаем статистику…</div>
          </div>

          <div v-else-if="statsPhase === 'error'" class="surface pad-lg">
            <div class="empty__text">Не удалось загрузить статистику.</div>
            <button class="btn btn--ghost" type="button" style="margin-top: 10px" @click="loadStats">
              Повторить
            </button>
          </div>

          <template v-else-if="statsPhase === 'ready' && stats">
            <div class="grid-3" style="gap: 10px; margin-bottom: 14px">
              <div class="stat">
                <span class="stat__num">{{ stats.total_answered }}</span>
                <span class="stat__label">ответов</span>
              </div>
              <div class="stat">
                <span class="stat__num">{{ stats.total_correct }}</span>
                <span class="stat__label">верных</span>
              </div>
              <div class="stat">
                <span class="stat__num stat__num--plus"
                  >{{ Math.round(stats.overall_accuracy) }}%</span
                >
                <span class="stat__label">точность</span>
              </div>
            </div>

            <div class="surface" style="overflow: hidden">
              <div
                v-for="t in stats.topics"
                :key="t.slug"
                class="br-row"
                data-test="stat-topic"
              >
                <span class="br-row__name">{{ t.title }}</span>
                <span class="mono t-soft">{{ t.correct }}/{{ t.answered }}</span>
                <span class="mono" :class="t.accuracy >= 70 ? 'diff-plus' : 'diff-minus'"
                  >{{ Math.round(t.accuracy) }}%</span
                >
              </div>
              <div v-if="stats.topics.length === 0" class="empty__text" style="padding: 16px">
                Пока нет данных по темам — сыграйте несколько дуэлей.
              </div>
            </div>
          </template>
        </div>
        <div style="height: 24px"></div>
      </div>
    </main>

    <TabBar active="profile" />
  </div>
</template>

<style scoped>
.prof-grid {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 16px;
  align-items: start;
}
@media (max-width: 640px) {
  .prof-grid {
    grid-template-columns: 1fr;
  }
}
.pill--pro {
  background: var(--plus-bg, rgb(31 157 85 / 0.12));
  color: var(--plus);
  font: 700 11px var(--font-mono);
  letter-spacing: 0.08em;
}
.br-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 12px;
  align-items: center;
  padding: 11px 16px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.br-row:last-child {
  border-bottom: 0;
}
.br-row__name {
  font: 600 13px var(--font-body);
}
.br-row .mono {
  font-variant-numeric: tabular-nums;
}
</style>
