import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';

interface NavItem {
  to: string;
  label: string;
  /** Точное совпадение (для индексного «Обзор» по «/»). */
  end?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    title: '// аналитика',
    items: [
      { to: '/', label: 'Обзор', end: true },
      { to: '/dashboard', label: 'Дашборд' },
    ],
  },
  {
    title: '// контент',
    items: [
      { to: '/tasks', label: 'Задачи' },
      { to: '/tasks/new', label: 'Редактор задачи' },
    ],
  },
  {
    title: '// люди',
    items: [{ to: '/users', label: 'Пользователи' }],
  },
  {
    title: '// соревнования',
    items: [{ to: '/tournaments', label: 'Турниры' }],
  },
  {
    title: '// система',
    items: [{ to: '/flags', label: 'Фиче-флаги' }],
  },
];

function navClass({ isActive }: { isActive: boolean }): string {
  return isActive ? 'adm-side__item is-on' : 'adm-side__item';
}

export function Shell(): React.JSX.Element {
  const { logout } = useAuth();

  return (
    <div className="adm">
      <aside className="adm__side-wrap">
        <nav className="adm-side">
          <div className="adm-side__brand">
            <span className="vs">VS</span>Admin
          </div>
          {SECTIONS.map((section) => (
            <div key={section.title}>
              <div className="adm-side__sec">{section.title}</div>
              {section.items.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
          <button type="button" className="adm-side__item" onClick={() => void logout()}>
            ← Выйти
          </button>
        </nav>
      </aside>

      <div className="adm__main">
        <Outlet />
      </div>
    </div>
  );
}

/** Топбар-обёртка (adm__top) — переиспользуется страницами. */
export function TopBar({ children }: { children?: React.ReactNode }): React.JSX.Element {
  const { user } = useAuth();
  const initials = (user?.username ?? 'AD').slice(0, 2).toUpperCase();
  return (
    <header className="adm__top">
      {children}
      <span className="ava ava--3 ava--sm">{initials}</span>
    </header>
  );
}
