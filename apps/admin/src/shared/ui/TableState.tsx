import { ApiRequestError } from '@/shared/api/client';

interface TableStateProps {
  colSpan: number;
  loading: boolean;
  error: unknown;
  empty: boolean;
  emptyText?: string;
}

function errorText(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 403) return 'Недостаточно прав для просмотра.';
    return error.message;
  }
  return 'Не удалось загрузить данные.';
}

/**
 * Единые состояния таблицы (loading/empty/error) строкой внутри <tbody>.
 * Возвращает null, когда есть данные — тогда таблица рисует строки сама.
 */
export function TableStateRow({
  colSpan,
  loading,
  error,
  empty,
  emptyText = 'Ничего не найдено.',
}: TableStateProps): React.JSX.Element | null {
  if (loading) {
    return (
      <tr>
        <td colSpan={colSpan}>
          <div className="adm-state">Загрузка…</div>
        </td>
      </tr>
    );
  }
  if (error) {
    return (
      <tr>
        <td colSpan={colSpan}>
          <div className="adm-state adm-state--error">{errorText(error)}</div>
        </td>
      </tr>
    );
  }
  if (empty) {
    return (
      <tr>
        <td colSpan={colSpan}>
          <div className="adm-state">{emptyText}</div>
        </td>
      </tr>
    );
  }
  return null;
}
