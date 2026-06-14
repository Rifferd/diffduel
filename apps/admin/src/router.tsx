import { createBrowserRouter } from 'react-router-dom';
import { Shell } from '@/shared/ui/Shell';
import { RequireAdmin } from '@/auth/RequireAdmin';
import { OverviewPage } from '@/pages/OverviewPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { TasksPage } from '@/pages/tasks/TasksPage';
import { TaskEditPage } from '@/pages/tasks/TaskEditPage';
import { UsersPage } from '@/pages/users/UsersPage';
import { TournamentsPage } from '@/pages/tournaments/TournamentsPage';
import { FlagsPage } from '@/pages/FlagsPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <RequireAdmin>
        <Shell />
      </RequireAdmin>
    ),
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'tasks', element: <TasksPage /> },
      { path: 'tasks/new', element: <TaskEditPage /> },
      { path: 'tasks/:taskId', element: <TaskEditPage /> },
      { path: 'users', element: <UsersPage /> },
      { path: 'tournaments', element: <TournamentsPage /> },
      { path: 'flags', element: <FlagsPage /> },
    ],
  },
]);
