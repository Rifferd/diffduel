import { useMemo, useState } from 'react';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table';
import type { TournamentCreate, TournamentStatus, TournamentSummary } from '@diffduel/contracts';
import { TopBar } from '@/shared/ui/Shell';
import { TableStateRow } from '@/shared/ui/TableState';
import { useToast } from '@/shared/ui/ToastContext';
import { useDocumentTitle } from '@/shared/ui/useDocumentTitle';
import { useTopics } from '@/shared/api/queries';
import {
  useCreateTournamentMutation,
  useGrantEntryMutation,
  useTournamentStatusMutation,
  useTournamentsQuery,
} from './useTournaments';

const STATUS_PILL: Record<TournamentStatus, string> = {
  upcoming: 'pill pill--soon',
  active: 'pill pill--live',
  finished: 'pill pill--done',
};

const STATUS_FLOW: TournamentStatus[] = ['upcoming', 'active', 'finished'];

function shortId(id: string): string {
  return `#${id.slice(0, 8)}`;
}

function money(value: string): string {
  const n = Number(value);
  return `${Number.isFinite(n) ? n.toLocaleString('ru-RU') : value} ₽`;
}

interface CreateForm {
  title: string;
  topicId: string;
  taskCount: number;
  startsAt: string;
  endsAt: string;
  entryFee: number;
  prizePool: number;
}

const EMPTY_FORM: CreateForm = {
  title: '',
  topicId: '',
  taskCount: 10,
  startsAt: '',
  endsAt: '',
  entryFee: 0,
  prizePool: 0,
};

const columnHelper = createColumnHelper<TournamentSummary>();

export function TournamentsPage(): React.JSX.Element {
  useDocumentTitle('турниры');
  const { notify, notifyError } = useToast();

  const tournaments = useTournamentsQuery();
  const topics = useTopics();
  const createMutation = useCreateTournamentMutation();
  const statusMutation = useTournamentStatusMutation();
  const grantMutation = useGrantEntryMutation();

  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);
  const [grantUserId, setGrantUserId] = useState<Record<string, string>>({});

  const topicLabel = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of topics.data ?? []) map.set(t.id, t.title);
    return map;
  }, [topics.data]);

  function nextStatusOf(s: TournamentStatus): TournamentStatus | null {
    const i = STATUS_FLOW.indexOf(s);
    return i >= 0 && i < STATUS_FLOW.length - 1 ? STATUS_FLOW[i + 1] : null;
  }

  function changeStatus(id: string, status: TournamentStatus): void {
    statusMutation.mutate(
      { id, status },
      {
        onSuccess: () => notify(`Статус → ${status}.`),
        onError: notifyError,
      },
    );
  }

  function grantEntry(id: string): void {
    const userId = (grantUserId[id] ?? '').trim();
    if (!userId) {
      notify('Укажите user_id для выдачи входа.', 'error');
      return;
    }
    grantMutation.mutate(
      { id, userId },
      {
        onSuccess: () => {
          notify('Вход выдан пользователю.');
          setGrantUserId((m) => ({ ...m, [id]: '' }));
        },
        onError: notifyError,
      },
    );
  }

  function submitCreate(): void {
    if (form.title.trim().length === 0) {
      notify('Заполните название турнира.', 'error');
      return;
    }
    if (!form.topicId) {
      notify('Выберите тему.', 'error');
      return;
    }
    if (!form.startsAt) {
      notify('Укажите дату старта.', 'error');
      return;
    }
    const payload: TournamentCreate = {
      title: form.title.trim(),
      topic_id: form.topicId,
      starts_at: new Date(form.startsAt).toISOString(),
      ends_at: form.endsAt ? new Date(form.endsAt).toISOString() : null,
      entry_fee: form.entryFee,
      prize_pool: form.prizePool,
      task_count: form.taskCount,
      status: 'upcoming',
    };
    createMutation.mutate(payload, {
      onSuccess: () => {
        notify('Турнир создан (upcoming).');
        setForm(EMPTY_FORM);
      },
      onError: notifyError,
    });
  }

  const columns = useMemo(
    () => [
      columnHelper.accessor('id', {
        header: 'ID',
        cell: (info) => <span className="num">{shortId(info.getValue())}</span>,
      }),
      columnHelper.accessor('title', { header: 'Название' }),
      columnHelper.accessor('topic_id', {
        header: 'Тема',
        cell: (info) => {
          const id = info.getValue();
          return id ? (topicLabel.get(id) ?? '—') : 'all-lang';
        },
      }),
      columnHelper.accessor('entries_count', {
        header: 'Уч.',
        cell: (info) => <span className="num">{info.getValue()}</span>,
      }),
      columnHelper.accessor('entry_fee', {
        header: 'Взнос',
        cell: (info) => <span className="num">{money(info.getValue())}</span>,
      }),
      columnHelper.accessor('prize_pool', {
        header: 'Фонд',
        cell: (info) => <span className="num">{money(info.getValue())}</span>,
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
          const next = nextStatusOf(t.status);
          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {next && (
                <button
                  type="button"
                  className="btn btn--duel"
                  style={{ padding: '4px 10px' }}
                  disabled={statusMutation.isPending}
                  onClick={() => changeStatus(t.id, next)}
                >
                  → {next}
                </button>
              )}
              <span style={{ display: 'flex', gap: 4 }}>
                <input
                  type="text"
                  placeholder="user_id"
                  aria-label={`user_id для ${t.title}`}
                  value={grantUserId[t.id] ?? ''}
                  onChange={(e) =>
                    setGrantUserId((m) => ({ ...m, [t.id]: e.target.value }))
                  }
                  style={{ width: 120, fontSize: 12 }}
                />
                <button
                  type="button"
                  className="btn btn--ghost"
                  style={{ padding: '4px 10px' }}
                  disabled={grantMutation.isPending}
                  onClick={() => grantEntry(t.id)}
                >
                  Выдать вход
                </button>
              </span>
            </div>
          );
        },
      }),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [topicLabel, statusMutation.isPending, grantMutation.isPending, grantUserId],
  );

  const rows = tournaments.data ?? [];
  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <>
      <TopBar>
        <span style={{ flex: 1 }} />
      </TopBar>
      <main className="adm__content">
        <h1 style={{ font: '800 24px var(--font-display)', fontStretch: '110%', marginBottom: 14 }}>
          Турниры · {rows.length}
        </h1>

        <div className="surface" style={{ overflow: 'hidden', marginBottom: 18 }}>
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
                loading={tournaments.isLoading}
                error={tournaments.error}
                empty={rows.length === 0}
                emptyText="Турниров пока нет."
              />
              {!tournaments.isLoading &&
                !tournaments.error &&
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
        </div>

        <h2 style={{ font: '800 18px var(--font-display)', fontStretch: '110%', marginBottom: 12 }}>
          Новый турнир
        </h2>
        <form
          className="edit-form"
          style={{ maxWidth: 640 }}
          onSubmit={(e) => {
            e.preventDefault();
            submitCreate();
          }}
        >
          <label className="field">
            <span className="field__label">Название</span>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            />
          </label>

          <div className="row-2">
            <label className="field">
              <span className="field__label">Тема</span>
              <select
                value={form.topicId}
                onChange={(e) => setForm((f) => ({ ...f, topicId: e.target.value }))}
              >
                <option value="" disabled>
                  — выбрать —
                </option>
                {(topics.data ?? []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Кол-во задач</span>
              <input
                type="number"
                min={1}
                max={50}
                value={form.taskCount}
                onChange={(e) => setForm((f) => ({ ...f, taskCount: Number(e.target.value) }))}
              />
            </label>
          </div>

          <div className="row-2">
            <label className="field">
              <span className="field__label">Старт</span>
              <input
                type="datetime-local"
                value={form.startsAt}
                onChange={(e) => setForm((f) => ({ ...f, startsAt: e.target.value }))}
              />
            </label>
            <label className="field">
              <span className="field__label">Окончание (необязательно)</span>
              <input
                type="datetime-local"
                value={form.endsAt}
                onChange={(e) => setForm((f) => ({ ...f, endsAt: e.target.value }))}
              />
            </label>
          </div>

          <div className="row-2">
            <label className="field">
              <span className="field__label">Взнос (₽)</span>
              <input
                type="number"
                min={0}
                value={form.entryFee}
                onChange={(e) => setForm((f) => ({ ...f, entryFee: Number(e.target.value) }))}
              />
            </label>
            <label className="field">
              <span className="field__label">Призовой фонд (₽)</span>
              <input
                type="number"
                min={0}
                value={form.prizePool}
                onChange={(e) => setForm((f) => ({ ...f, prizePool: Number(e.target.value) }))}
              />
            </label>
          </div>

          <div>
            <button
              type="submit"
              className="btn btn--duel"
              style={{ padding: '8px 14px' }}
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? 'Создаём…' : '+ Создать турнир'}
            </button>
          </div>
        </form>
      </main>
    </>
  );
}
