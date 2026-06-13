import { useAuth } from './AuthContext';
import { useDocumentTitle } from '@/shared/ui/useDocumentTitle';

export function AccessDenied(): React.JSX.Element {
  useDocumentTitle('доступ запрещён');
  const { logout } = useAuth();
  return (
    <div className="adm">
      <main
        className="adm__content"
        style={{ maxWidth: 420, margin: '0 auto', alignSelf: 'center', width: '100%' }}
      >
        <span className="eyebrow">// 403</span>
        <h1 style={{ font: '800 24px var(--font-display)', fontStretch: '110%', margin: '8px 0' }}>
          Доступ запрещён
        </h1>
        <p className="t-soft" style={{ fontSize: 14, marginBottom: 18 }}>
          Эта учётная запись не имеет роли модератора или администратора. Войдите под аккаунтом с
          нужными правами.
        </p>
        <button className="btn btn--ghost" type="button" onClick={() => void logout()}>
          Выйти
        </button>
      </main>
    </div>
  );
}
