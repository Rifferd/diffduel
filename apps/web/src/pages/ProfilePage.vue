<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { meApi } from '@/shared/api/endpoints';
import { ApiRequestError } from '@/shared/api/client';
import AppNav from '@/components/AppNav.vue';
import TabBar from '@/components/TabBar.vue';

const auth = useAuthStore();

const user = computed(() => auth.user);
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

        <div class="section prof-grid">
          <div style="display: grid; gap: 14px">
            <div class="surface pad-lg">
              <div class="section__head" style="margin: 0 0 12px">
                <h2 style="font-size: 16px">Динамика Эло</h2>
              </div>
              <div class="empty">
                <div class="empty__icon">∅</div>
                <div class="empty__title">Данных пока нет</div>
                <div class="empty__text">Сыграйте несколько дуэлей, чтобы увидеть динамику.</div>
              </div>
            </div>
          </div>

          <div style="display: grid; gap: 14px">
            <div class="grid-2" style="gap: 10px">
              <div class="stat"><span class="stat__num">0</span><span class="stat__label">дуэлей</span></div>
              <div class="stat"><span class="stat__num">—</span><span class="stat__label">точность</span></div>
            </div>
          </div>
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
</style>
