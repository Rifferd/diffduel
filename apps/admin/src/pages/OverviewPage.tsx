import { useQuery } from '@tanstack/react-query';
import { metricsApi } from '@/shared/api/endpoints';
import { TopBar } from '@/shared/ui/Shell';
import { useDocumentTitle } from '@/shared/ui/useDocumentTitle';

const numberFmt = new Intl.NumberFormat('ru-RU');

/** Соответствует design/pages/admin/shell.html — каркас «Обзор». */
export function OverviewPage(): React.JSX.Element {
  useDocumentTitle('обзор');
  const metrics = useQuery({
    queryKey: ['metrics', 'overview'],
    queryFn: () => metricsApi.overview(),
  });

  const m = metrics.data;
  const fmt = (v: number | undefined): string => (v === undefined ? '—' : numberFmt.format(v));

  return (
    <>
      <TopBar>
        <label className="field">
          <input type="search" placeholder="Поиск по задачам, игрокам, ID…" />
        </label>
        <span className="adm__sp" style={{ flex: 1 }} />
      </TopBar>
      <main className="adm__content">
        <h1 style={{ font: '800 24px var(--font-display)', fontStretch: '110%', marginBottom: 6 }}>
          Обзор
        </h1>
        <p className="t-soft" style={{ fontSize: 14, marginBottom: 18 }}>
          Каркас админки: сайдбар, топбар с поиском, контент-зона. Утилитарный стиль на тех же
          токенах — без VS-сплитов и display-шрифта в данных.
        </p>

        <div className="grid-4" style={{ marginBottom: 18 }}>
          <div className="stat" style={{ textAlign: 'left' }}>
            <span className="stat__num" style={{ fontSize: 22 }}>
              {fmt(m?.users)}
            </span>
            <span className="stat__label">пользователей</span>
          </div>
          <div className="stat" style={{ textAlign: 'left' }}>
            <span className="stat__num" style={{ fontSize: 22 }}>
              {fmt(m?.duels_24h)}
            </span>
            <span className="stat__label">дуэлей / 24ч</span>
          </div>
          <div className="stat" style={{ textAlign: 'left' }}>
            <span className="stat__num stat__num--plus" style={{ fontSize: 22 }}>
              {fmt(m?.duels_7d)}
            </span>
            <span className="stat__label">дуэлей / 7д</span>
          </div>
          <div className="stat" style={{ textAlign: 'left' }}>
            <span className="stat__num" style={{ fontSize: 22 }}>
              {fmt(m?.published_tasks)}
            </span>
            <span className="stat__label">published задач</span>
          </div>
        </div>

        <div className="surface" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>
            <strong style={{ font: '700 14px var(--font-display)', fontStretch: '110%' }}>
              Сводка
            </strong>
          </div>
          <table className="adm-table">
            <thead>
              <tr>
                <th scope="col">Метрика</th>
                <th scope="col">Значение</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Активные подписки</td>
                <td className="num">{fmt(m?.active_subscriptions)}</td>
              </tr>
              <tr>
                <td>Опубликованные задачи</td>
                <td className="num">{fmt(m?.published_tasks)}</td>
              </tr>
              <tr>
                <td>Дуэлей за 7 дней</td>
                <td className="num">{fmt(m?.duels_7d)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
}
