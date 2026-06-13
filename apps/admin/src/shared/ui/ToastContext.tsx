import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { ApiRequestError } from '@/shared/api/client';

type ToastKind = 'error' | 'success';

interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastContextValue {
  notify(message: string, kind?: ToastKind): void;
  /** Показать ошибку API/сети с понятным текстом (учитывает 403). */
  notifyError(error: unknown): void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

function messageFromError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 403) {
      return 'Недостаточно прав для этого действия.';
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return 'Что-то пошло не так. Попробуйте позже.';
}

export function ToastProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const notify = useCallback(
    (message: string, kind: ToastKind = 'success') => {
      const id = nextId.current++;
      setToasts((prev) => [...prev, { id, kind, message }]);
      setTimeout(() => remove(id), 4000);
    },
    [remove],
  );

  const notifyError = useCallback(
    (error: unknown) => {
      notify(messageFromError(error), 'error');
    },
    [notify],
  );

  const value = useMemo<ToastContextValue>(() => ({ notify, notifyError }), [notify, notifyError]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast--${t.kind}`} onClick={() => remove(t.id)}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- хук соседствует с провайдером намеренно
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
