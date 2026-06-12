import { createRouter, createWebHistory } from 'vue-router';
import type { RouteRecordRaw } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { public: true, title: 'DiffDuel — вход' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/pages/RegisterPage.vue'),
    meta: { public: true, title: 'DiffDuel — регистрация' },
  },
  {
    path: '/',
    name: 'home',
    component: () => import('@/pages/HomePage.vue'),
    meta: { title: 'DiffDuel — главная' },
  },
  {
    path: '/training',
    name: 'training',
    component: () => import('@/pages/TrainingPage.vue'),
    meta: { title: 'DiffDuel — тренировка' },
  },
  {
    path: '/duel',
    name: 'duel',
    component: () => import('@/pages/DuelPage.vue'),
    meta: { title: 'DiffDuel — дуэль' },
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/pages/ProfilePage.vue'),
    meta: { title: 'DiffDuel — мой профиль' },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/pages/SettingsPage.vue'),
    meta: { title: 'DiffDuel — настройки' },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();

  // Дождаться стартового тихого refresh, чтобы не редиректить вслепую.
  if (!auth.ready) {
    await auth.bootstrap();
  }

  const isPublic = to.meta.public === true;

  if (!auth.isAuthenticated && !isPublic) {
    return { name: 'login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : undefined };
  }

  if (auth.isAuthenticated && (to.name === 'login' || to.name === 'register')) {
    return { name: 'home' };
  }

  return true;
});

router.afterEach((to) => {
  const title = to.meta.title;
  if (typeof title === 'string') {
    document.title = title;
  }
});
