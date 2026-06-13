<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { ApiRequestError } from '@/shared/api/client';

type Status = 'pending' | 'logged-in' | 'confirmed-other' | 'error' | 'no-token';

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const status = ref<Status>('pending');
/** Код для ввода на устройстве регистрации (ответ другого устройства). */
const code = ref<string | null>(null);
const errorMessage = ref<string | null>(null);

function mapLinkError(err: ApiRequestError): string {
  if (err.status === 429) {
    return 'Слишком много попыток. Подождите немного и попробуйте снова.';
  }
  if (err.code === 'invalid_token' || err.code === 'token_expired') {
    return 'Ссылка недействительна или истекла.';
  }
  return 'Ссылка недействительна или истекла.';
}

onMounted(async () => {
  const token = typeof route.query.token === 'string' ? route.query.token : '';
  if (!token) {
    status.value = 'no-token';
    return;
  }
  try {
    const res = await auth.verifyLink(token);
    if (res.logged_in) {
      status.value = 'logged-in';
    } else {
      code.value = res.code ?? null;
      status.value = 'confirmed-other';
    }
  } catch (err) {
    errorMessage.value =
      err instanceof ApiRequestError ? mapLinkError(err) : 'Ссылка недействительна или истекла.';
    status.value = 'error';
  }
});

async function goApp(): Promise<void> {
  await router.push('/app');
}
</script>

<template>
  <main class="auth">
    <div class="auth__card" data-test="verify-link-card">
      <RouterLink class="auth__logo" to="/"><span class="vs">VS</span>DiffDuel</RouterLink>

      <template v-if="status === 'pending'">
        <h1 class="auth__title">Подтверждаем…</h1>
        <p class="auth__sub">Секунду, проверяем ссылку из письма.</p>
      </template>

      <template v-else-if="status === 'logged-in'">
        <div class="auth__check" aria-hidden="true">✓</div>
        <h1 class="auth__title" style="color: var(--plus)">Почта подтверждена</h1>
        <p class="auth__sub">Готово — вы вошли в DiffDuel.</p>
        <button class="btn btn--duel btn--block" type="button" data-test="enter" @click="goApp">
          Войти в DiffDuel
        </button>
      </template>

      <template v-else-if="status === 'confirmed-other'">
        <div class="auth__check" aria-hidden="true">✓</div>
        <h1 class="auth__title" style="color: var(--plus)">Почта подтверждена!</h1>
        <p class="auth__sub">
          Вернитесь на устройство, где регистрировались, и введите код из письма.
        </p>
        <div
          v-if="code"
          class="auth__code"
          data-test="other-device-code"
          style="
            font-family: var(--font-mono);
            font-size: 28px;
            letter-spacing: 0.35em;
            text-align: center;
            padding: 14px;
            border: 1px solid var(--line);
            border-radius: var(--radius);
            background: var(--plus-bg);
            color: var(--plus);
          "
        >
          {{ code }}
        </div>
      </template>

      <template v-else-if="status === 'error'">
        <h1 class="auth__title" style="color: var(--minus)">Не получилось</h1>
        <p class="auth__sub" data-test="link-error">{{ errorMessage }}</p>
        <RouterLink class="btn btn--duel btn--block" to="/verify-email"
          >Ввести код вручную</RouterLink
        >
        <p class="auth__foot"><RouterLink to="/login">Вернуться ко входу</RouterLink></p>
      </template>

      <template v-else>
        <h1 class="auth__title">Нет ссылки</h1>
        <p class="auth__sub">В ссылке нет токена. Откройте письмо ещё раз или введите код вручную.</p>
        <RouterLink class="btn btn--duel btn--block" to="/verify-email"
          >Ввести код вручную</RouterLink
        >
        <p class="auth__foot"><RouterLink to="/login">Вернуться ко входу</RouterLink></p>
      </template>
    </div>
  </main>
</template>

<style scoped>
.auth__check {
  width: 56px;
  height: 56px;
  margin: 0 auto;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--plus-bg);
  color: var(--plus);
  font-size: 30px;
  font-weight: 800;
}
</style>
