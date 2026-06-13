import type { ReactNode } from 'react';
import { useAuth } from './AuthContext';
import { LoginPage } from './LoginPage';
import { AccessDenied } from './AccessDenied';

/**
 * Гейт по роли: пока идёт стартовый refresh — спиннер; нет сессии — экран входа;
 * есть сессия, но роль не moderator/admin — экран «Доступ запрещён».
 */
export function RequireAdmin({ children }: { children: ReactNode }): React.JSX.Element {
  const { status, isAdminRole } = useAuth();

  if (status === 'loading') {
    return (
      <div className="adm">
        <main className="adm__content">
          <div className="adm-state">Загрузка…</div>
        </main>
      </div>
    );
  }

  if (status === 'anonymous') {
    return <LoginPage />;
  }

  if (!isAdminRole) {
    return <AccessDenied />;
  }

  return <>{children}</>;
}
