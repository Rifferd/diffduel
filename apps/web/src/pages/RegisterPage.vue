<script setup lang="ts">
import { reactive, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import { z } from 'zod';
import { useAuthStore } from '@/stores/auth';
import { ApiRequestError } from '@/shared/api/client';

const schema = z.object({
  username: z.string().min(3, 'Минимум 3 символа.').max(32, 'Слишком длинный ник.'),
  email: z.string().email('Похоже, в адресе опечатка — нет домена.'),
  password: z
    .string()
    .min(10, 'Минимум 10 символов.')
    .regex(/[a-zA-Z]/, 'Нужны буквы.')
    .regex(/[0-9]/, 'Нужны цифры.'),
  accept: z.literal(true, { errorMap: () => ({ message: 'Нужно принять оферту.' }) }),
});

const auth = useAuthStore();
const router = useRouter();

const form = reactive({ username: '', email: '', password: '', accept: false });
const fieldErrors = reactive<{
  username?: string;
  email?: string;
  password?: string;
  accept?: string;
}>({});
const formError = ref<string | null>(null);
const submitting = ref(false);

function mapApiError(err: ApiRequestError): string {
  if (err.status === 429) {
    return 'Слишком много попыток. Подождите немного и попробуйте снова.';
  }
  if (err.status === 409) {
    return 'Такой ник или email уже заняты.';
  }
  return err.message;
}

async function onSubmit(): Promise<void> {
  fieldErrors.username = undefined;
  fieldErrors.email = undefined;
  fieldErrors.password = undefined;
  fieldErrors.accept = undefined;
  formError.value = null;

  const parsed = schema.safeParse(form);
  if (!parsed.success) {
    for (const issue of parsed.error.issues) {
      const key = issue.path[0];
      if (key === 'username' || key === 'email' || key === 'password' || key === 'accept') {
        fieldErrors[key] = issue.message;
      }
    }
    return;
  }

  submitting.value = true;
  try {
    await auth.register({
      username: parsed.data.username,
      email: parsed.data.email,
      password: parsed.data.password,
    });
    await router.push('/app');
  } catch (err) {
    if (err instanceof ApiRequestError) {
      formError.value = mapApiError(err);
    } else {
      formError.value = 'Не удалось зарегистрироваться. Попробуйте позже.';
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
      <h1 class="auth__title">Создать аккаунт</h1>
      <p class="auth__sub">Первая дуэль — через минуту</p>

      <div class="auth__divider">// по почте</div>

      <label class="field" :class="{ 'field--error': fieldErrors.username }">
        <span class="field__label">Ник</span>
        <input v-model="form.username" type="text" placeholder="username" autocomplete="username" />
        <span v-if="fieldErrors.username" class="field__hint">{{ fieldErrors.username }}</span>
      </label>

      <label class="field" :class="{ 'field--error': fieldErrors.email }">
        <span class="field__label">Email</span>
        <input v-model="form.email" type="email" placeholder="you@team.dev" autocomplete="email" />
        <span v-if="fieldErrors.email" class="field__hint">{{ fieldErrors.email }}</span>
      </label>

      <label class="field" :class="{ 'field--error': fieldErrors.password }">
        <span class="field__label">Пароль</span>
        <input
          v-model="form.password"
          type="password"
          placeholder="минимум 10 символов"
          autocomplete="new-password"
        />
        <span class="field__hint" :class="{ '': !fieldErrors.password }">{{
          fieldErrors.password ?? 'Минимум 10 символов, буквы и цифры'
        }}</span>
      </label>

      <label class="check">
        <input v-model="form.accept" type="checkbox" />
        <span class="check__box"></span>
        <span style="font-size: 13px"
          >Принимаю <a class="link-plus" href="#" @click.prevent>оферту</a> и политику данных</span
        >
      </label>
      <span v-if="fieldErrors.accept" class="field__hint" style="color: var(--minus)">{{
        fieldErrors.accept
      }}</span>

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
        {{ submitting ? 'Создаём…' : 'Создать аккаунт' }}
      </button>

      <p class="auth__foot">Уже есть аккаунт? <RouterLink to="/login">Войти</RouterLink></p>
    </form>
  </main>
</template>
