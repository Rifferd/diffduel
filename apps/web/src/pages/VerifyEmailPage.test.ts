import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import VerifyEmailPage from './VerifyEmailPage.vue';
import { authApi, meApi } from '@/shared/api/endpoints';
import { useAuthStore } from '@/stores/auth';
import { ApiRequestError } from '@/shared/api/client';

const pushMock = vi.fn();
let routeQuery: Record<string, string> = {};
vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ query: routeQuery }),
}));

describe('VerifyEmailPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    pushMock.mockReset();
    routeQuery = { email: 'anton@team.dev' };
    vi.restoreAllMocks();
  });

  it('успешная верификация → setSession + редирект на /app', async () => {
    const verifySpy = vi
      .spyOn(authApi, 'verifyEmail')
      .mockResolvedValue({ access_token: 'tok42', token_type: 'bearer', expires_in: 900 });
    vi.spyOn(meApi, 'get').mockResolvedValue({
      id: 'u1',
      username: 'anton_dev',
      avatar_key: null,
      avatar_url: null,
      role: 'user',
      created_at: '2026-03-01T00:00:00Z',
      email: 'anton@team.dev',
      is_pro: false,
    });

    const wrapper = mount(VerifyEmailPage);
    await wrapper.find('[data-test="code-input"]').setValue('123456');
    await wrapper.find('form').trigger('submit.prevent');
    await flushPromises();

    expect(verifySpy).toHaveBeenCalledWith({ email: 'anton@team.dev', code: '123456' });
    expect(useAuthStore().accessToken).toBe('tok42');
    expect(pushMock).toHaveBeenCalledWith('/app');
  });

  it('invalid_code → человекочитаемая ошибка, без редиректа', async () => {
    vi.spyOn(authApi, 'verifyEmail').mockRejectedValue(
      new ApiRequestError(400, 'invalid_code', 'bad'),
    );

    const wrapper = mount(VerifyEmailPage);
    await wrapper.find('[data-test="code-input"]').setValue('000000');
    await wrapper.find('form').trigger('submit.prevent');
    await flushPromises();

    expect(wrapper.find('[data-test="form-error"]').text()).toContain('Неверный код');
    expect(pushMock).not.toHaveBeenCalled();
  });

  it('нечисловой ввод фильтруется до 6 цифр', async () => {
    const wrapper = mount(VerifyEmailPage);
    const input = wrapper.find('[data-test="code-input"]');
    await input.setValue('12ab34cd567');
    expect((input.element as HTMLInputElement).value).toBe('123456');
  });

  it('без email в query — предлагает зарегистрироваться, поля кода нет', () => {
    routeQuery = {};
    const wrapper = mount(VerifyEmailPage);
    expect(wrapper.find('[data-test="code-input"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('Зарегистрируйтесь');
  });
});
