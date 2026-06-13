import { useMemo, useState } from 'react';
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table';
import type { AdminUser, AdminUserList } from '@diffduel/contracts';
import { adminUsersApi } from '@/shared/api/endpoints';
import { useAuth } from '@/auth/AuthContext';
import { TopBar } from '@/shared/ui/Shell';
import { TableStateRow } from '@/shared/ui/TableState';
import { useToast } from '@/shared/ui/ToastContext';
import { useDocumentTitle } from '@/shared/ui/useDocumentTitle';

const USERS_PAGE_SIZE = 20;
const dateFmt = new Intl.DateTimeFormat('ru-RU');

const columnHelper = createColumnHelper<AdminUser>();

function useUsersQuery(q: string, page: number): UseQueryResult<AdminUserList> {
  return useQuery({
    queryKey: ['admin', 'users', { q, page }],
    queryFn: () => adminUsersApi.list({ q, page, pageSize: USERS_PAGE_SIZE }),
    placeholderData: (prev) => prev,
  });
}

export function UsersPage(): React.JSX.Element {
  useDocumentTitle('пользователи');
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const { notify, notifyError } = useToast();
  const queryClient = useQueryClient();

  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AdminUser | null>(null);
  const [banReason, setBanReason] = useState('');
  const [banTarget, setBanTarget] = useState<AdminUser | null>(null);

  const users = useUsersQuery(q, page);

  const banMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      adminUsersApi.ban(id, { reason }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      notify('Игрок забанен.');
      setBanTarget(null);
      setBanReason('');
    },
    onError: notifyError,
  });

  const unbanMutation = useMutation({
    mutationFn: (id: string) => adminUsersApi.unban(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      notify('Игрок разбанен.');
    },
    onError: notifyError,
  });

  const columns = useMemo(
    () => [
      columnHelper.accessor('username', {
        header: 'Ник',
        cell: (info) => <b>{info.getValue()}</b>,
      }),
      columnHelper.accessor('email', { header: 'Email' }),
      columnHelper.accessor('role', {
        header: 'Роль',
        cell: (info) => <span className="pill">{info.getValue()}</span>,
      }),
      columnHelper.accessor('banned_at', {
        header: 'Статус',
        cell: (info) =>
          info.getValue() ? (
            <span className="pill pill--down">banned</span>
          ) : (
            <span className="pill pill--soon">active</span>
          ),
      }),
      columnHelper.display({
        id: 'actions',
        header: 'Действия',
        cell: ({ row }) => {
          const u = row.original;
          return (
            <span style={{ display: 'flex', gap: 6 }}>
              <button
                type="button"
                className="btn btn--ghost"
                style={{ padding: '4px 10px' }}
                onClick={() => setSelected(u)}
              >
                Карточка
              </button>
              {u.banned_at ? (
                <button
                  type="button"
                  className="btn btn--ghost"
                  style={{ padding: '4px 10px' }}
                  disabled={!isAdmin || unbanMutation.isPending}
                  title={isAdmin ? undefined : 'Доступно только администратору'}
                  onClick={() => unbanMutation.mutate(u.id)}
                >
                  Разбанить
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn--danger"
                  style={{ padding: '4px 10px' }}
                  disabled={!isAdmin}
                  title={isAdmin ? undefined : 'Доступно только администратору'}
                  onClick={() => setBanTarget(u)}
                >
                  Забанить
                </button>
              )}
            </span>
          );
        },
      }),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [isAdmin, unbanMutation.isPending],
  );

  const rows = users.data?.items ?? [];
  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel() });
  const total = users.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / USERS_PAGE_SIZE));

  return (
    <>
      <TopBar>
        <label className="field">
          <input
            type="search"
            placeholder="Поиск по нику, email, ID…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <span style={{ flex: 1 }} />
      </TopBar>
      <main className="adm__content">
        <h1 style={{ font: '800 24px var(--font-display)', fontStretch: '110%', marginBottom: 14 }}>
          Пользователи · {total}
        </h1>

        {!isAdmin && (
          <p className="t-soft" style={{ fontSize: 13, marginBottom: 12 }}>
            Вы вошли как модератор — бан и разбан доступны только администратору.
          </p>
        )}

        <div className="users-grid">
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
                  loading={users.isLoading}
                  error={users.error}
                  empty={rows.length === 0}
                  emptyText="Пользователи не найдены."
                />
                {!users.isLoading &&
                  !users.error &&
                  table.getRowModel().rows.map((row, i) => (
                    <tr key={row.id} className={i % 2 === 1 ? 'adm-table__row--alt' : undefined}>
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

          {selected && (
            <div className="surface ucard">
              <div className="ucard__head">
                <span className="ava ava--3">
                  {selected.username.slice(0, 2).toUpperCase()}
                </span>
                <div>
                  <div style={{ font: '700 16px var(--font-display)', fontStretch: '110%' }}>
                    {selected.username}
                  </div>
                  <div className="mono t-soft" style={{ fontSize: 11 }}>
                    {selected.email}
                  </div>
                </div>
              </div>
              <div>
                <div className="ucard__row">
                  <span className="t-soft">Роль</span>
                  <span className="mono">{selected.role}</span>
                </div>
                <div className="ucard__row">
                  <span className="t-soft">Регистрация</span>
                  <span className="mono">
                    {dateFmt.format(new Date(selected.created_at))}
                  </span>
                </div>
                <div className="ucard__row">
                  <span className="t-soft">Статус</span>
                  <span className="mono">{selected.banned_at ? 'banned' : 'active'}</span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="btn btn--ghost"
                  style={{ flex: 1, padding: 8 }}
                  onClick={() => setSelected(null)}
                >
                  Закрыть
                </button>
                {!selected.banned_at && (
                  <button
                    type="button"
                    className="btn btn--danger"
                    style={{ flex: 1, padding: 8 }}
                    disabled={!isAdmin}
                    onClick={() => setBanTarget(selected)}
                  >
                    Забанить
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {banTarget && (
          <div style={{ marginTop: 20, maxWidth: 440 }}>
            <div className="modal" role="dialog" aria-modal="true" style={{ maxWidth: 'none' }}>
              <div className="modal__head">
                <h2 className="modal__title">Забанить {banTarget.username}?</h2>
                <button
                  type="button"
                  className="modal__close"
                  aria-label="Закрыть"
                  onClick={() => setBanTarget(null)}
                >
                  ×
                </button>
              </div>
              <div className="modal__body">
                Игрок потеряет доступ к рейтинговым дуэлям. Укажите причину — она попадёт в журнал
                модерации.
              </div>
              <div style={{ padding: '0 22px' }}>
                <input
                  className="field"
                  type="text"
                  placeholder="Причина: накрутка рейтинга"
                  style={{ width: '100%' }}
                  value={banReason}
                  onChange={(e) => setBanReason(e.target.value)}
                />
              </div>
              <div className="modal__foot">
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => setBanTarget(null)}
                >
                  Отмена
                </button>
                <button
                  type="button"
                  className="btn btn--danger"
                  disabled={banReason.trim().length === 0 || banMutation.isPending}
                  onClick={() =>
                    banMutation.mutate({ id: banTarget.id, reason: banReason.trim() })
                  }
                >
                  Забанить
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
