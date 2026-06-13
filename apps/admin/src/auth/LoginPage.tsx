import { useState, type FormEvent } from 'react';
import { useAuth } from './AuthContext';
import { useToast } from '@/shared/ui/ToastContext';
import { useDocumentTitle } from '@/shared/ui/useDocumentTitle';

export function LoginPage(): React.JSX.Element {
  useDocumentTitle('вход');
  const { login } = useAuth();
  const { notifyError } = useToast();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setSubmitting(true);
    try {
      await login({ email, password });
    } catch (error) {
      notifyError(error);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="adm">
      <main
        className="adm__content"
        style={{ maxWidth: 380, margin: '0 auto', alignSelf: 'center', width: '100%' }}
      >
        <div className="adm-side__brand" style={{ marginBottom: 18 }}>
          <span className="vs">VS</span>Admin
        </div>
        <h1
          style={{ font: '800 24px var(--font-display)', fontStretch: '110%', marginBottom: 14 }}
        >
          Вход в админку
        </h1>
        <form
          className="edit-form"
          onSubmit={(e) => {
            void onSubmit(e);
          }}
        >
          <label className="field">
            <span className="field__label">Email</span>
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="field">
            <span className="field__label">Пароль</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <button className="btn btn--duel" type="submit" disabled={submitting}>
            {submitting ? 'Входим…' : 'Войти'}
          </button>
        </form>
      </main>
    </div>
  );
}
