import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { AdminTask, AdminTaskList, TopicPublic } from '@diffduel/contracts';

const listMock = vi.fn<(p: unknown) => Promise<AdminTaskList>>();
const publishMock = vi.fn<(id: string) => Promise<AdminTask>>();
const rejectMock = vi.fn<(id: string) => Promise<AdminTask>>();
const topicsListMock = vi.fn<() => Promise<TopicPublic[]>>();

vi.mock('@/shared/api/endpoints', () => ({
  adminTasksApi: {
    list: (p: unknown) => listMock(p),
    publish: (id: string) => publishMock(id),
    reject: (id: string) => rejectMock(id),
  },
  topicsApi: { list: () => topicsListMock() },
}));

// useAuth is consumed by TopBar — stub it to a logged-in admin.
vi.mock('@/auth/AuthContext', () => ({
  useAuth: () => ({
    status: 'authenticated',
    user: { username: 'boss', role: 'admin' },
    isAdminRole: true,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

import { TasksPage } from './TasksPage';
import { ToastProvider } from '@/shared/ui/ToastContext';

const TOPIC: TopicPublic = {
  id: '11111111-1111-1111-1111-111111111111',
  slug: 'js',
  title: 'JavaScript',
};

function makeTask(overrides: Partial<AdminTask> = {}): AdminTask {
  return {
    id: '22222222-2222-2222-2222-222222222222',
    topic_id: TOPIC.id,
    difficulty: 2,
    type: 'quiz',
    body: { question: 'Что выведет typeof null?', options: ['object', 'null'] },
    answer: { correct: 0 },
    explanation: null,
    status: 'review',
    author_id: null,
    version: 1,
    ...overrides,
  };
}

function renderPage(): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <TasksPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe('TasksPage', () => {
  beforeEach(() => {
    listMock.mockReset();
    publishMock.mockReset();
    rejectMock.mockReset();
    topicsListMock.mockReset();
    topicsListMock.mockResolvedValue([TOPIC]);
  });

  it('renders rows from the mocked API', async () => {
    listMock.mockResolvedValue({ items: [makeTask()], page: 1, page_size: 20, total: 1 });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText('Что выведет typeof null?')).toBeInTheDocument(),
    );
    // «JavaScript» встречается и в фильтре, и в ячейке темы — проверяем ячейку (td).
    const topicCell = screen
      .getAllByText('JavaScript')
      .find((el) => el.tagName === 'TD');
    expect(topicCell).toBeInTheDocument();
    // «review» есть и в фильтре, и в статус-пилюле строки — проверяем пилюлю в td.
    const statusPill = screen
      .getAllByText('review')
      .find((el) => el.closest('td') !== null);
    expect(statusPill).toBeInTheDocument();
  });

  it('publish action calls the publish endpoint with the task id', async () => {
    const task = makeTask();
    listMock.mockResolvedValue({ items: [task], page: 1, page_size: 20, total: 1 });
    publishMock.mockResolvedValue({ ...task, status: 'published' });

    renderPage();

    const button = await screen.findByRole('button', { name: 'Опубликовать' });
    await userEvent.click(button);

    await waitFor(() => expect(publishMock).toHaveBeenCalledWith(task.id));
    expect(rejectMock).not.toHaveBeenCalled();
  });
});
