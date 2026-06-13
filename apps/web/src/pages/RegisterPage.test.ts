import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import RegisterPage from './RegisterPage.vue';
import { authApi, meApi } from '@/shared/api/endpoints';
import { useAuthStore } from '@/stores/auth';

const pushMock = vi.fn();
vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ query: {} }),
}));

async function fillValidForm(wrapper: ReturnType<typeof mount>): Promise<void> {
  await wrapper.find('input[type="text"]').setValue('anton_dev');
  await wrapper.find('input[type="email"]').setValue('anton@team.dev');
  await wrapper.find('input[type="password"]').setValue('password123');
  await wrapper.find('input[type="checkbox"]').setValue(true);
  await wrapper.find('form').trigger('submit.prevent');
  await flushPromises();
}

describe('RegisterPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    pushMock.mockReset();
    vi.restoreAllMocks();
  });

  it('режим ON: verification_required → редирект на /verify-email с email, без логина', async () => {
    const registerSpy = vi
      .spyOn(authApi, 'register')
      .mockResolvedValue({ verification_required: true });
    const meSpy = vi.spyOn(meApi, 'get');

    const wrapper = mount(RegisterPage);
    await fillValidForm(wrapper);

    expect(registerSpy).toHaveBeenCalledWith({
      username: 'anton_dev',
      email: 'anton@team.dev',
      password: 'password123',
    });
    expect(meSpy).not.toHaveBeenCalled();
    expect(useAuthStore().accessToken).toBeNull();
    expect(pushMock).toHaveBeenCalledWith({
      path: '/verify-email',
      query: { email: 'anton@team.dev' },
    });
  });

  it('режим OFF: verification_required:false → авто-логин и редирект на /app', async () => {
    vi.spyOn(authApi, 'register').mockResolvedValue({
      verification_required: false,
      access_token: 'abc123',
      token_type: 'bearer',
      expires_in: 900,
    });
    vi.spyOn(meApi, 'get').mockResolvedValue({
      id: 'u1',
      username: 'anton_dev',
      avatar_key: null,
      avatar_url: null,
      role: 'user',
      created_at: '2026-03-01T00:00:00Z',
      email: 'anton@team.dev',
    });

    const wrapper = mount(RegisterPage);
    await fillValidForm(wrapper);

    expect(useAuthStore().accessToken).toBe('abc123');
    expect(pushMock).toHaveBeenCalledWith('/app');
  });
});
