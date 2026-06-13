import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { FeatureFlagOut } from '@diffduel/contracts';
import { flagsApi } from '@/shared/api/endpoints';
import { TopBar } from '@/shared/ui/Shell';
import { useToast } from '@/shared/ui/ToastContext';
import { useDocumentTitle } from '@/shared/ui/useDocumentTitle';

function payloadSummary(payload: FeatureFlagOut['payload']): string {
  if (payload === null || payload === undefined) return '';
  const keys = Object.keys(payload);
  if (keys.length === 0) return '{}';
  return JSON.stringify(payload);
}

export function FlagsPage(): React.JSX.Element {
  useDocumentTitle('фиче-флаги');
  const { notify, notifyError } = useToast();
  const queryClient = useQueryClient();

  const flags = useQuery({
    queryKey: ['admin', 'feature-flags'],
    queryFn: () => flagsApi.list(),
  });

  const toggle = useMutation({
    mutationFn: (flag: FeatureFlagOut) =>
      flagsApi.upsert(flag.key, { enabled: !flag.enabled, payload: flag.payload }),
    onMutate: async (flag) => {
      await queryClient.cancelQueries({ queryKey: ['admin', 'feature-flags'] });
      const prev = queryClient.getQueryData<FeatureFlagOut[]>(['admin', 'feature-flags']);
      if (prev) {
        queryClient.setQueryData<FeatureFlagOut[]>(
          ['admin', 'feature-flags'],
          prev.map((f) => (f.key === flag.key ? { ...f, enabled: !f.enabled } : f)),
        );
      }
      return { prev };
    },
    onError: (error, _flag, context) => {
      if (context?.prev) queryClient.setQueryData(['admin', 'feature-flags'], context.prev);
      notifyError(error);
    },
    onSuccess: (updated) => {
      notify(`Флаг ${updated.key}: ${updated.enabled ? 'включён' : 'выключен'}.`);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'feature-flags'] });
    },
  });

  const items = flags.data ?? [];

  return (
    <>
      <TopBar>
        <label className="field">
          <input type="search" placeholder="Поиск по ключу флага…" />
        </label>
        <span style={{ flex: 1 }} />
      </TopBar>
      <main className="adm__content">
        <h1 style={{ font: '800 24px var(--font-display)', fontStretch: '110%', marginBottom: 6 }}>
          Фиче-флаги
        </h1>
        <p className="t-soft" style={{ fontSize: 14, marginBottom: 18 }}>
          Постепенная раскатка фич. Тоггл включает/выключает флаг (кэшируется в Redis на 30с).
        </p>

        {flags.isLoading && <div className="adm-state">Загрузка…</div>}
        {flags.isError && (
          <div className="adm-state adm-state--error">Не удалось загрузить флаги.</div>
        )}
        {!flags.isLoading && !flags.isError && items.length === 0 && (
          <div className="adm-state">Флагов пока нет.</div>
        )}

        <div style={{ display: 'grid', gap: 12, maxWidth: 720 }}>
          {items.map((flag) => (
            <div className="flag" key={flag.key}>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={flag.enabled}
                  disabled={toggle.isPending}
                  onChange={() => toggle.mutate(flag)}
                />
                <span className="toggle__track" />
              </label>
              <div className="flag__main">
                <div className="flag__name">{flag.key}</div>
                <div className="flag__key">{payloadSummary(flag.payload) || flag.key}</div>
              </div>
              <span className={`flag__pct ${flag.enabled ? 'diff-plus' : ''}`}>
                {flag.enabled ? 'on' : 'off'}
              </span>
            </div>
          ))}
        </div>
      </main>
    </>
  );
}
