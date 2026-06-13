import { describe, it, expect, beforeEach, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { router } from './index';
import { useAuthStore } from '@/stores/auth';

describe('router guards', () => {
  beforeEach(async () => {
    // jsdom не реализует scrollTo — глушим, чтобы scrollBehavior не шумел.
    vi.stubGlobal('scrollTo', vi.fn());
    setActivePinia(createPinia());
    // bootstrap не должен реально ходить в сеть в этих тестах.
    vi.spyOn(useAuthStore(), 'bootstrap').mockResolvedValue();
  });

  it('гость видит публичный лендинг на / без редиректа на /login', async () => {
    const auth = useAuthStore();
    auth.ready = true; // сессии нет — гость
    await router.push('/');
    await router.isReady();
    expect(router.currentRoute.value.name).toBe('landing');
    expect(router.currentRoute.value.path).toBe('/');
  });

  it('гость с защищённого маршрута уходит на /login', async () => {
    const auth = useAuthStore();
    auth.ready = true;
    await router.push('/app');
    await router.isReady();
    expect(router.currentRoute.value.name).toBe('login');
  });

  it('авторизованный с / редиректится на /app', async () => {
    const auth = useAuthStore();
    auth.ready = true;
    auth.accessToken = 'token'; // isAuthenticated === true
    await router.push('/');
    await router.isReady();
    expect(router.currentRoute.value.path).toBe('/app');
    expect(router.currentRoute.value.name).toBe('home');
  });
});
