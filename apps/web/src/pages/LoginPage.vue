<script setup lang="ts">
import { reactive, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { z } from 'zod';
import { useAuthStore } from '@/stores/auth';
import { ApiRequestError } from '@/shared/api/client';

const schema = z.object({
  email: z.string().email('Похоже, в адресе опечатка.'),
  password: z.string().min(1, 'Введите пароль.'),
});

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const form = reactive({ email: '', password: '' });
const fieldErrors = reactive<{ email?: string; password?: string }>({});
const formError = ref<string | null>(null);
const submitting = ref(false);

function mapApiError(err: ApiRequestError): string {
  if (err.status === 429) {
    return 'Слишком много попыток. Подождите немного и попробуйте снова.';
  }
  return err.message;
}

async function onSubmit(): Promise<void> {
  fieldErrors.email = undefined;
  fieldErrors.password = undefined;
  formError.value = null;

  const parsed = schema.safeParse(form);
  if (!parsed.success) {
    for (const issue of parsed.error.issues) {
      const key = issue.path[0];
      if (key === 'email' || key === 'password') fieldErrors[key] = issue.message;
    }
    return;
  }

  submitting.value = true;
  try {
    await auth.login(parsed.data);
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/app';
    await router.push(redirect);
  } catch (err) {
    if (err instanceof ApiRequestError) {
      formError.value = mapApiError(err);
    } else {
      formError.value = 'Не удалось войти. Попробуйте позже.';
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="auth">
    <form class="auth__card" novalidate @submit.prevent="onSubmit">
      <RouterLink class="auth__logo" to="/"><span class="vs">VS</span>DiffDuel</RouterLink>
      <h1 class="auth__title">Вход в арену</h1>
      <p class="auth__sub">Докажи кодом, кто быстрее</p>

      <div class="auth__divider">// по почте</div>

      <label class="field" :class="{ 'field--error': fieldErrors.email }">
        <span class="field__label">Email</span>
        <input v-model="form.email" type="email" placeholder="you@team.dev" autocomplete="email" />
        <span v-if="fieldErrors.email" class="field__hint">{{ fieldErrors.email }}</span>
      </label>

      <label class="field" :class="{ 'field--error': fieldErrors.password }">
        <span class="field__label">Пароль</span>
        <input v-model="form.password" type="password" autocomplete="current-password" />
        <span v-if="fieldErrors.password" class="field__hint">{{ fieldErrors.password }}</span>
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

      <button class="btn btn--duel btn--block" type="submit" :disabled="submitting">
        {{ submitting ? 'Входим…' : 'Войти' }}
      </button>

      <p class="auth__foot">
        Нет аккаунта? <RouterLink to="/register">Зарегистрироваться</RouterLink>
      </p>
    </form>
  </main>
</template>
