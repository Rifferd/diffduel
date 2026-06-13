import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table';
import type { AdminTask, TaskStatus } from '@diffduel/contracts';
import { TopBar } from '@/shared/ui/Shell';
import { TableStateRow } from '@/shared/ui/TableState';
import { useToast } from '@/shared/ui/ToastContext';
import { useDocumentTitle } from '@/shared/ui/useDocumentTitle';
import { useTopics } from '@/shared/api/queries';
import { TASKS_PAGE_SIZE, useTaskStatusMutation, useTasksQuery } from './useTasks';

const STATUS_PILL: Record<TaskStatus, string> = {
  draft: 'pill pill--done',
  review: 'pill pill--down',
  published: 'pill pill--soon',
};

function shortId(id: string): string {
  return `#${id.slice(0, 8)}`;
}

function questionText(task: AdminTask): string {
  const body = task.body as { question?: unknown };
  return typeof body.question === 'string' ? body.question : '—';
}

const columnHelper = createColumnHelper<AdminTask>();

export function TasksPage(): React.JSX.Element {
  useDocumentTitle('задачи');
  const navigate = useNavigate();
  const { notifyError, notify } = useToast();

  const [status, setStatus] = useState<TaskStatus | ''>('');
  const [topicId, setTopicId] = useState('');
  const [page, setPage] = useState(1);

  const topics = useTopics();
  const params = useMemo(
    () => ({ status, topic: topicId, page, pageSize: TASKS_PAGE_SIZE }),
    [status, topicId, page],
  );
  const tasks = useTasksQuery(params);
  const statusMutation = useTaskStatusMutation(params);

  const topicLabel = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of topics.data ?? []) map.set(t.id, t.title);
    return map;
  }, [topics.data]);

  function runStatus(id: string, action: 'publish' | 'reject'): void {
    statusMutation.mutate(
      { id, action },
      {
        onSuccess: () => notify(action === 'publish' ? 'Задача опубликована.' : 'Задача отклонена.'),
        onError: (error) => notifyError(error),
      },
    );
  }

  const columns = useMemo(
    () => [
      columnHelper.accessor('id', {
        header: 'ID',
        cell: (info) => <span className="num">{shortId(info.getValue())}</span>,
      }),
      columnHelper.display({
        id: 'question',
        header: 'Текст',
        cell: ({ row }) => questionText(row.original),
      }),
      columnHelper.accessor('topic_id', {
        header: 'Тема',
        cell: (info) => topicLabel.get(info.getValue()) ?? '—',
      }),
      columnHelper.accessor('difficulty', {
        header: 'Сложн.',
        cell: (info) => <span className="num">{info.getValue()}</span>,
      }),
      columnHelper.accessor('status', {
        header: 'Статус',
        cell: (info) => {
          const s = info.getValue();
          return <span className={STATUS_PILL[s]}>{s}</span>;
        },
      }),
      columnHelper.display({
        id: 'actions',
        header: 'Действия',
        cell: ({ row }) => {
          const t = row.original;
          return (
            <span style={{ display: 'flex', gap: 6 }}>
              <Link className="btn btn--ghost" to={`/tasks/${t.id}`} style={{ padding: '4px 10px' }}>
                Открыть
              </Link>
              {t.status !== 'published' && (
                <button
                  type="button"
                  className="btn btn--duel"
                  style={{ padding: '4px 10px' }}
                  disabled={statusMutation.isPending}
                  onClick={() => runStatus(t.id, 'publish')}
                >
                  Опубликовать
                </button>
              )}
              {t.status === 'review' && (
                <button
                  type="button"
                  className="btn btn--ghost t-minus"
                  style={{ padding: '4px 10px' }}
                  disabled={statusMutation.isPending}
                  onClick={() => runStatus(t.id, 'reject')}
                >
                  Отклонить
                </button>
              )}
            </span>
          );
        },
      }),
    ],
    // runStatus/statusMutation stable enough per render; topicLabel drives recompute.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [topicLabel, statusMutation.isPending],
  );

  const rows = tasks.data?.items ?? [];
  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const total = tasks.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / TASKS_PAGE_SIZE));

  function changeStatus(next: TaskStatus | ''): void {
    setStatus(next);
    setPage(1);
  }
  function changeTopic(next: string): void {
    setTopicId(next);
    setPage(1);
  }

  return (
    <>
      <TopBar>
        <label className="field">
          <input type="search" placeholder="Поиск по тексту задачи…" />
        </label>
        <span style={{ flex: 1 }} />
        <button
          type="button"
          className="btn btn--duel"
          style={{ padding: '8px 14px' }}
          onClick={() => navigate('/tasks/new')}
        >
          + Новая задача
        </button>
      </TopBar>
      <main className="adm__content">
        <h1 style={{ font: '800 24px var(--font-display)', fontStretch: '110%', marginBottom: 14 }}>
          Задачи · {total}
        </h1>

        <div className="filters">
          <div className="seg" style={{ transform: 'scale(.92)', transformOrigin: 'left' }}>
            <button
              type="button"
              className={topicId === '' ? 'seg__opt is-on' : 'seg__opt'}
              onClick={() => changeTopic('')}
            >
              Все темы
            </button>
            {(topics.data ?? []).map((t) => (
              <button
                key={t.id}
                type="button"
                className={topicId === t.id ? 'seg__opt is-on' : 'seg__opt'}
                onClick={() => changeTopic(t.id)}
              >
                {t.title}
              </button>
            ))}
          </div>
          <span style={{ display: 'flex', gap: 6 }}>
            {(['draft', 'review', 'published'] as TaskStatus[]).map((s) => (
              <button
                key={s}
                type="button"
                className={`${STATUS_PILL[s]}${status === s ? ' is-on' : ''}`}
                style={{ cursor: 'pointer', opacity: status === '' || status === s ? 1 : 0.5 }}
                onClick={() => changeStatus(status === s ? '' : s)}
              >
                {s}
              </button>
            ))}
          </span>
        </div>

        <div className="surface" style={{ overflow: 'hidden' }}>
          <table className="adm-table">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((header) => (
                    <th key={header.id} scope="col">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              <TableStateRow
                colSpan={columns.length}
                loading={tasks.isLoading}
                error={tasks.error}
                empty={rows.length === 0}
                emptyText="Задач по фильтрам нет."
              />
              {!tasks.isLoading &&
                !tasks.error &&
                table.getRowModel().rows.map((row) => (
                  <tr key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
            </tbody>
          </table>
          <div className="pager">
            <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              ‹
            </button>
            <button className="is-on" type="button">
              {page}
            </button>
            <span className="t-soft mono" style={{ fontSize: 12, padding: '0 6px' }}>
              из {pageCount}
            </span>
            <button
              type="button"
              disabled={page >= pageCount}
              onClick={() => setPage((p) => p + 1)}
            >
              ›
            </button>
          </div>
        </div>
      </main>
    </>
  );
}
