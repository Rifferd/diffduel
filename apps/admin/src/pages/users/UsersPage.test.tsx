import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { AdminUser, AdminUserList, ProStatus } from '@diffduel/contracts';

const listMock = vi.fn<(p: unknown) => Promise<AdminUserList>>();
const grantProMock = vi.fn<(id: string, p: { days: number }) => Promise<ProStatus>>();
const revokeProMock = vi.fn<(id: string) => Promise<ProStatus>>();

vi.mock('@/shared/api/endpoints', () => ({
  adminUsersApi: {
    list: (p: unknown) => listMock(p),
    ban: vi.fn(),
    unban: vi.fn(),
    grantPro: (id: string, p: { days: number }) => grantProMock(id, p),
    revokePro: (id: string) => revokeProMock(id),
  },
}));

vi.mock('@/auth/AuthContext', () => ({
  useAuth: () => ({
    status: 'authenticated',
    user: { username: 'boss', role: 'admin' },
    isAdminRole: true,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

import { UsersPage } from './UsersPage';
import { ToastProvider } from '@/shared/ui/ToastContext';

function makeUser(overrides: Partial<AdminUser> = {}): AdminUser {
  return {
    id: '33333333-3333-3333-3333-333333333333',
    email: 'anton@team.dev',
    username: 'anton_dev',
    role: 'user',
    created_at: '2026-03-12T00:00:00Z',
    banned_at: null,
    ...overrides,
  };
}

function renderPage(): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <UsersPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe('UsersPage Pro actions', () => {
  beforeEach(() => {
    listMock.mockReset();
    grantProMock.mockReset();
    revokeProMock.mockReset();
  });

  it('«Выдать Pro» зовёт grant-pro эндпоинт с днями и оптимистично показывает Pro', async () => {
    const user = makeUser();
    listMock.mockResolvedValue({ items: [user], page: 1, page_size: 20, total: 1 });
    grantProMock.mockResolvedValue({ is_pro: true, current_period_end: '2026-07-14T00:00:00Z' });

    renderPage();

    const grantBtn = await screen.findByRole('button', { name: 'Выдать Pro' });
    await userEvent.click(grantBtn);

    await waitFor(() => expect(grantProMock).toHaveBeenCalledWith(user.id, { days: 30 }));
    expect(revokeProMock).not.toHaveBeenCalled();
    // После выдачи появляется кнопка «Снять Pro».
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Снять Pro' })).toBeInTheDocument(),
    );
  });

  it('«Снять Pro» зовёт revoke-pro эндпоинт', async () => {
    const user = makeUser();
    listMock.mockResolvedValue({ items: [user], page: 1, page_size: 20, total: 1 });
    grantProMock.mockResolvedValue({ is_pro: true, current_period_end: '2026-07-14T00:00:00Z' });
    revokeProMock.mockResolvedValue({ is_pro: false, current_period_end: null });

    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Выдать Pro' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Снять Pro' }));

    await waitFor(() => expect(revokeProMock).toHaveBeenCalledWith(user.id));
  });
});
