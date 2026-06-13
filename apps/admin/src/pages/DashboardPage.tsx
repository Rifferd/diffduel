import { useQuery } from '@tanstack/react-query';
import { metricsApi } from '@/shared/api/endpoints';
import { TopBar } from '@/shared/ui/Shell';
import { useDocumentTitle } from '@/shared/ui/useDocumentTitle';

const numberFmt = new Intl.NumberFormat('ru-RU');

interface Kpi {
  label: string;
  value: number | undefined;
  delta: string;
  deltaClass: string;
}

/** Соответствует design/pages/admin/dashboard.html — KPI-карточки из /admin/metrics/overview. */
export function DashboardPage(): React.JSX.Element {
  useDocumentTitle('дашборд');
  const metrics = useQuery({
    queryKey: ['metrics', 'overview'],
    queryFn: () => metricsApi.overview(),
  });
  const m = metrics.data;
  const fmt = (v: number | undefined): string => (v === undefined ? '—' : numberFmt.format(v));

  const kpis: Kpi[] = [
    { label: 'Пользователей', value: m?.users, delta: 'всего', deltaClass: 'diff-plus' },
    { label: 'Дуэлей / 24ч', value: m?.duels_24h, delta: 'за сутки', deltaClass: 'diff-plus' },
    { label: 'Дуэлей / 7д', value: m?.duels_7d, delta: 'за неделю', deltaClass: 'diff-plus' },
    {
      label: 'Активные подписки',
      value: m?.active_subscriptions,
      delta: 'Pro',
      deltaClass: 'diff-plus',
    },
  ];

  return (
    <>
      <TopBar>
        <label className="field">
          <input type="search" placeholder="Поиск…" />
        </label>
        <span style={{ flex: 1 }} />
      </TopBar>
      <main className="adm__content">
        <h1 style={{ font: '800 24px var(--font-display)', fontStretch: '110%', marginBottom: 18 }}>
          Дашборд
        </h1>

        <div className="grid-4" style={{ marginBottom: 16 }}>
          {kpis.map((k) => (
            <div key={k.label} className="surface kpi">
              <div className="kpi__top">
                <span className="kpi__label">{k.label}</span>
              </div>
              <div className="kpi__num">{metrics.isError ? '—' : fmt(k.value)}</div>
              <div className={`kpi__delta ${k.deltaClass}`}>{k.delta}</div>
            </div>
          ))}
        </div>

        <div className="surface" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>
            <strong style={{ font: '700 14px var(--font-display)', fontStretch: '110%' }}>
              Опубликованные задачи
            </strong>
          </div>
          <table className="adm-table">
            <thead>
              <tr>
                <th scope="col">Показатель</th>
                <th scope="col" className="num">
                  Значение
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Published задач</td>
                <td className="num">{fmt(m?.published_tasks)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
}
