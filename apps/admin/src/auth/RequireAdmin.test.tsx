import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { TokenResponse, UserMe } from '@diffduel/contracts';

const refreshMock = vi.fn<() => Promise<TokenResponse>>();
const meMock = vi.fn<() => Promise<UserMe>>();
const logoutMock = vi.fn<() => Promise<void>>();

vi.mock('@/shared/api/endpoints', () => ({
  authApi: {
    refresh: () => refreshMock(),
    login: vi.fn(),
    logout: () => logoutMock(),
  },
  meApi: { get: () => meMock() },
}));

// Import after mock is registered.
import { AuthProvider } from './AuthContext';
import { RequireAdmin } from './RequireAdmin';
import { ToastProvider } from '@/shared/ui/ToastContext';

function renderGate(): void {
  render(
    <ToastProvider>
      <AuthProvider>
        <MemoryRouter>
          <RequireAdmin>
            <div>SECRET ADMIN CONTENT</div>
          </RequireAdmin>
        </MemoryRouter>
      </AuthProvider>
    </ToastProvider>,
  );
}

function makeUser(role: UserMe['role']): UserMe {
  return {
    id: '00000000-0000-0000-0000-000000000001',
    username: 'tester',
    avatar_key: null,
    avatar_url: null,
    role,
    created_at: '2026-01-01T00:00:00Z',
    email: 'tester@example.com',
    is_pro: false,
  };
}

describe('RequireAdmin gate', () => {
  beforeEach(() => {
    refreshMock.mockReset();
    meMock.mockReset();
    logoutMock.mockReset();
    logoutMock.mockResolvedValue(undefined);
  });
  afterEach(() => vi.clearAllMocks());

  it('shows access-denied screen for a non-admin role', async () => {
    refreshMock.mockResolvedValue({ access_token: 'tok', token_type: 'bearer', expires_in: 900 });
    meMock.mockResolvedValue(makeUser('user'));

    renderGate();

    await waitFor(() => expect(screen.getByText('Доступ запрещён')).toBeInTheDocument());
    expect(screen.queryByText('SECRET ADMIN CONTENT')).not.toBeInTheDocument();
  });

  it('renders admin content for an admin role', async () => {
    refreshMock.mockResolvedValue({ access_token: 'tok', token_type: 'bearer', expires_in: 900 });
    meMock.mockResolvedValue(makeUser('admin'));

    renderGate();

    await waitFor(() => expect(screen.getByText('SECRET ADMIN CONTENT')).toBeInTheDocument());
  });

  it('shows the login screen when there is no session', async () => {
    refreshMock.mockRejectedValue(new Error('no cookie'));

    renderGate();

    await waitFor(() => expect(screen.getByText('Вход в админку')).toBeInTheDocument());
    expect(screen.queryByText('SECRET ADMIN CONTENT')).not.toBeInTheDocument();
  });
});
