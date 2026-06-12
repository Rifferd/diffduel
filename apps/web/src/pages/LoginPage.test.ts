import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import LoginPage from './LoginPage.vue';
import { authApi, meApi } from '@/shared/api/endpoints';
import { useAuthStore } from '@/stores/auth';
import { ApiRequestError } from '@/shared/api/client';

const pushMock = vi.fn();
vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ query: {} }),
}));

describe('LoginPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    pushMock.mockReset();
    vi.restoreAllMocks();
  });

  it('submits credentials, stores access token, and redirects', async () => {
    const loginSpy = vi
      .spyOn(authApi, 'login')
      .mockResolvedValue({ access_token: 'abc123', token_type: 'bearer', expires_in: 900 });
    vi.spyOn(meApi, 'get').mockResolvedValue({
      id: 'u1',
      username: 'anton_dev',
      avatar_key: null,
      role: 'user',
      created_at: '2026-03-01T00:00:00Z',
      email: 'anton@team.dev',
    });

    const wrapper = mount(LoginPage);
    await wrapper.find('input[type="email"]').setValue('anton@team.dev');
    await wrapper.find('input[type="password"]').setValue('secret');
    await wrapper.find('form').trigger('submit.prevent');
    await flushPromises();

    expect(loginSpy).toHaveBeenCalledWith({ email: 'anton@team.dev', password: 'secret' });

    const auth = useAuthStore();
    expect(auth.accessToken).toBe('abc123');
    expect(auth.user?.username).toBe('anton_dev');
    expect(pushMock).toHaveBeenCalledWith('/');
  });

  it('shows a field error for an invalid email without calling the API', async () => {
    const loginSpy = vi.spyOn(authApi, 'login');

    const wrapper = mount(LoginPage);
    await wrapper.find('input[type="email"]').setValue('not-an-email');
    await wrapper.find('input[type="password"]').setValue('secret');
    await wrapper.find('form').trigger('submit.prevent');
    await flushPromises();

    expect(loginSpy).not.toHaveBeenCalled();
    expect(wrapper.find('.field--error').exists()).toBe(true);
  });

  it('maps a 429 rate-limit to a human-readable message', async () => {
    vi.spyOn(authApi, 'login').mockRejectedValue(
      new ApiRequestError(429, 'rate_limited', 'too many'),
    );

    const wrapper = mount(LoginPage);
    await wrapper.find('input[type="email"]').setValue('anton@team.dev');
    await wrapper.find('input[type="password"]').setValue('secret');
    await wrapper.find('form').trigger('submit.prevent');
    await flushPromises();

    expect(wrapper.find('[data-test="form-error"]').text()).toContain('Слишком много попыток');
  });
});
