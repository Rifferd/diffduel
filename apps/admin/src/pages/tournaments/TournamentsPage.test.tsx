import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { AdminTournament, TopicPublic, TournamentSummary } from '@diffduel/contracts';

const listMock = vi.fn<(s?: unknown) => Promise<TournamentSummary[]>>();
const createMock = vi.fn<(p: unknown) => Promise<AdminTournament>>();
const updateMock = vi.fn<(id: string, p: unknown) => Promise<AdminTournament>>();
const grantMock = vi.fn<(id: string, u: string) => Promise<unknown>>();
const topicsListMock = vi.fn<() => Promise<TopicPublic[]>>();

vi.mock('@/shared/api/endpoints', () => ({
  adminTournamentsApi: {
    list: (s?: unknown) => listMock(s),
    create: (p: unknown) => createMock(p),
    update: (id: string, p: unknown) => updateMock(id, p),
    grantEntry: (id: string, u: string) => grantMock(id, u),
  },
  topicsApi: { list: () => topicsListMock() },
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

import { TournamentsPage } from './TournamentsPage';
import { ToastProvider } from '@/shared/ui/ToastContext';

const TOPIC: TopicPublic = {
  id: '11111111-1111-1111-1111-111111111111',
  slug: 'sql',
  title: 'SQL',
};

function makeTournament(over: Partial<TournamentSummary> = {}): TournamentSummary {
  return {
    id: '22222222-2222-2222-2222-222222222222',
    title: 'Пятничный блиц',
    topic_id: TOPIC.id,
    starts_at: '2026-06-20T19:00:00Z',
    ends_at: null,
    entry_fee: '0',
    prize_pool: '10000',
    status: 'upcoming',
    entries_count: 12,
    ...over,
  };
}

function renderPage(): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <TournamentsPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe('TournamentsPage', () => {
  beforeEach(() => {
    listMock.mockReset();
    createMock.mockReset();
    updateMock.mockReset();
    grantMock.mockReset();
    topicsListMock.mockReset();
    topicsListMock.mockResolvedValue([TOPIC]);
  });

  it('рендерит список турниров из мок-API', async () => {
    listMock.mockResolvedValue([makeTournament()]);
    renderPage();
    await waitFor(() => expect(screen.getByText('Пятничный блиц')).toBeInTheDocument());
  });

  it('создание турнира зовёт POST /admin/tournaments с заполненными полями', async () => {
    listMock.mockResolvedValue([]);
    createMock.mockResolvedValue({
      id: 'new-id',
      title: 'Кубок DiffDuel',
      topic_id: TOPIC.id,
      starts_at: '2026-07-01T18:00:00Z',
      ends_at: null,
      entry_fee: '0',
      prize_pool: '5000',
      status: 'upcoming',
      task_ids: [],
    });

    renderPage();
    await waitFor(() => expect(topicsListMock).toHaveBeenCalled());

    await userEvent.type(screen.getByLabelText('Название'), 'Кубок DiffDuel');
    await userEvent.selectOptions(screen.getByLabelText('Тема'), TOPIC.id);
    const startInput = screen.getByLabelText('Старт');
    await userEvent.type(startInput, '2026-07-01T18:00');

    await userEvent.click(screen.getByRole('button', { name: /Создать турнир/ }));

    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    const payload = createMock.mock.calls[0][0] as Record<string, unknown>;
    expect(payload.title).toBe('Кубок DiffDuel');
    expect(payload.topic_id).toBe(TOPIC.id);
    expect(payload.status).toBe('upcoming');
    expect(typeof payload.starts_at).toBe('string');
  });

  it('смена статуса зовёт update с следующим статусом', async () => {
    listMock.mockResolvedValue([makeTournament({ status: 'upcoming' })]);
    updateMock.mockResolvedValue({
      id: '22222222-2222-2222-2222-222222222222',
      title: 'Пятничный блиц',
      topic_id: TOPIC.id,
      starts_at: '2026-06-20T19:00:00Z',
      ends_at: null,
      entry_fee: '0',
      prize_pool: '10000',
      status: 'active',
      task_ids: [],
    });

    renderPage();
    const button = await screen.findByRole('button', { name: '→ active' });
    await userEvent.click(button);

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith('22222222-2222-2222-2222-222222222222', {
        status: 'active',
      }),
    );
  });
});
