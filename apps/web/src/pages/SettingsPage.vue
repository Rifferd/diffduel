<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { meApi } from '@/shared/api/endpoints';
import { ApiRequestError } from '@/shared/api/client';

const auth = useAuthStore();
const router = useRouter();

const username = ref('');
watch(
  () => auth.user,
  (u) => {
    if (u) username.value = u.username;
  },
  { immediate: true },
);

const email = computed(() => auth.user?.email ?? '');
const saving = ref(false);
const error = ref<string | null>(null);
const okMsg = ref<string | null>(null);

async function save(): Promise<void> {
  error.value = null;
  okMsg.value = null;
  const name = username.value.trim();
  if (name.length < 3) {
    error.value = 'Минимум 3 символа.';
    return;
  }
  saving.value = true;
  try {
    const updated = await meApi.update({ username: name });
    auth.user = updated;
    okMsg.value = 'Сохранено.';
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

async function logout(): Promise<void> {
  await auth.logout();
  await router.push('/login');
}
</script>

<template>
  <div class="app">
    <nav class="appnav">
      <div class="wrap appnav__in">
        <RouterLink class="nav__logo" to="/profile"><span class="vs">VS</span>DiffDuel</RouterLink>
        <span class="appnav__sp"></span>
        <RouterLink class="appnav__link" to="/profile">← Профиль</RouterLink>
      </div>
    </nav>

    <main class="app__main">
      <div class="wrap set">
        <div class="page-head" style="padding-bottom: 0"><h1>Настройки</h1></div>

        <div class="surface set-card">
          <h2>Профиль</h2>
          <label class="field">
            <span class="field__label">Ник</span>
            <input v-model="username" type="text" />
          </label>
          <label class="field">
            <span class="field__label">Email</span>
            <input :value="email" type="email" disabled />
          </label>
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
          <div style="display: flex; justify-content: flex-end">
            <button class="btn btn--duel" type="button" :disabled="saving" @click="save">
              {{ saving ? 'Сохраняем…' : 'Сохранить' }}
            </button>
          </div>
        </div>

        <div class="surface set-card">
          <h2>Сессия</h2>
          <div style="display: flex; justify-content: flex-end">
            <button class="btn btn--ghost" type="button" @click="logout">Выйти</button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.set {
  max-width: 680px;
  margin: 0 auto;
  padding: 8px 0 40px;
  display: grid;
  gap: 18px;
}
.set-card {
  padding: 22px;
  display: grid;
  gap: 14px;
}
.set-card h2 {
  font: 700 16px var(--font-display);
  font-stretch: 110%;
}
</style>
