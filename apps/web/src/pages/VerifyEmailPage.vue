<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { authApi } from '@/shared/api/endpoints';
import { ApiRequestError } from '@/shared/api/client';

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const email = computed(() => (typeof route.query.email === 'string' ? route.query.email : ''));
const notice = computed(() => (typeof route.query.notice === 'string' ? route.query.notice : ''));
const hasEmail = computed(() => email.value.length > 0);

const code = ref('');
const formError = ref<string | null>(null);
const submitting = ref(false);

// Кулдаун повторной отправки (спека: не чаще 1/60с на email).
const RESEND_COOLDOWN = 60;
const cooldown = ref(0);
const resending = ref(false);
const resendNote = ref<string | null>(null);
let cooldownTimer: ReturnType<typeof setInterval> | null = null;

onUnmounted(() => {
  if (cooldownTimer) clearInterval(cooldownTimer);
});

function startCooldown(): void {
  cooldown.value = RESEND_COOLDOWN;
  if (cooldownTimer) clearInterval(cooldownTimer);
  cooldownTimer = setInterval(() => {
    cooldown.value -= 1;
    if (cooldown.value <= 0 && cooldownTimer) {
      clearInterval(cooldownTimer);
      cooldownTimer = null;
    }
  }, 1000);
}

/** Оставляем только цифры, максимум 6 — авто-формат поля кода. */
function onCodeInput(event: Event): void {
  const raw = (event.target as HTMLInputElement).value;
  code.value = raw.replace(/\D/g, '').slice(0, 6);
}

function mapVerifyError(err: ApiRequestError): string {
  if (err.status === 429) {
    return 'Слишком много попыток. Подождите немного и попробуйте снова.';
  }
  switch (err.code) {
    case 'invalid_code':
      return 'Неверный код. Проверьте письмо и попробуйте ещё раз.';
    case 'code_expired':
      return 'Код истёк. Запросите новый.';
    case 'too_many_attempts':
      return 'Слишком много попыток. Запросите новый код.';
    default:
      return err.message;
  }
}

async function onSubmit(): Promise<void> {
  formError.value = null;
  resendNote.value = null;

  if (code.value.length !== 6) {
    formError.value = 'Введите 6-значный код из письма.';
    return;
  }

  submitting.value = true;
  try {
    await auth.verifyEmail(email.value, code.value);
    await router.push('/app');
  } catch (err) {
    if (err instanceof ApiRequestError) {
      formError.value = mapVerifyError(err);
    } else {
      formError.value = 'Не удалось подтвердить почту. Попробуйте позже.';
    }
  } finally {
    submitting.value = false;
  }
}

async function onResend(): Promise<void> {
  if (cooldown.value > 0 || resending.value) return;
  formError.value = null;
  resendNote.value = null;
  resending.value = true;
  try {
    await authApi.resendCode(email.value);
    startCooldown();
    resendNote.value = 'Новый код отправлен на почту.';
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 429) {
      startCooldown();
      formError.value = 'Слишком часто. Подождите минуту перед повторной отправкой.';
    } else {
      formError.value = 'Не удалось отправить код. Попробуйте позже.';
    }
  } finally {
    resending.value = false;
  }
}
</script>

<template>
  <main class="auth">
    <form class="auth__card" novalidate @submit.prevent="onSubmit">
      <RouterLink class="auth__logo" to="/"><span class="vs">VS</span>DiffDuel</RouterLink>
      <h1 class="auth__title">Подтвердите почту</h1>

      <template v-if="hasEmail">
        <p class="auth__sub">Мы отправили 6-значный код на<br /><b>{{ email }}</b></p>

        <p
          v-if="notice"
          class="field__hint"
          role="status"
          style="color: var(--plus); text-align: center"
          data-test="notice"
        >
          {{ notice }}
        </p>

        <div class="auth__divider">// код из письма</div>

        <label class="field" :class="{ 'field--error': formError }">
          <span class="field__label">Код подтверждения</span>
          <input
            :value="code"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            placeholder="123456"
            maxlength="6"
            style="
              text-align: center;
              letter-spacing: 0.4em;
              font-family: var(--font-mono);
              font-size: 22px;
            "
            data-test="code-input"
            @input="onCodeInput"
          />
        </label>

        <p
          v-if="formError"
          class="field__hint"
          role="alert"
          style="color: var(--minus); margin-top: -4px"
          data-test="form-error"
        >
          {{ formError }}
        </p>
        <p
          v-else-if="resendNote"
          class="field__hint"
          role="status"
          style="color: var(--plus); margin-top: -4px"
          data-test="resend-note"
        >
          {{ resendNote }}
        </p>

        <button class="btn btn--duel btn--block" type="submit" :disabled="submitting">
          {{ submitting ? 'Проверяем…' : 'Подтвердить' }}
        </button>

        <p class="auth__foot">
          Не пришёл код?
          <a
            v-if="cooldown === 0"
            class="link-plus"
            href="#"
            data-test="resend"
            @click.prevent="onResend"
            >{{ resending ? 'Отправляем…' : 'Выслать повторно' }}</a
          >
          <span v-else style="color: var(--ink-soft)" data-test="resend-cooldown"
            >Повторно через {{ cooldown }}&nbsp;с</span
          >
        </p>
      </template>

      <template v-else>
        <p class="auth__sub">
          Мы не знаем, какую почту подтверждать. Зарегистрируйтесь или войдите снова.
        </p>
        <RouterLink class="btn btn--duel btn--block" to="/register">Зарегистрироваться</RouterLink>
        <p class="auth__foot">Уже есть аккаунт? <RouterLink to="/login">Войти</RouterLink></p>
      </template>
    </form>
  </main>
</template>
