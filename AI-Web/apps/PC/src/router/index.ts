import { createRouter, createWebHashHistory } from 'vue-router';
import useUserStore from '../store/modules'; 

const SidebarLayout = () => import('../components/pages/sidebar.vue');
const Chat = () => import('../pages/chat.vue');
const Memory = () => import('../pages/Memory.vue');
const login = () => import('../pages/Login.vue');
const Setting = () => import('../pages/Setting.vue');

const routes = [
  {
    path: '/',
    component: SidebarLayout,
    children: [
      {
        path: '',
        component: Chat,
        name: 'chat',
        meta: { requiresAuth: true },
      },
      {
        path: 'memory',
        component: Memory,
        name: 'Memory',
        meta: { requiresAuth: true },
      },
      {
        path: 'seting',
        component: Setting,
        name: 'seting',
        meta: { requiresAuth: true },
      },
    ],
  },
  {
    path: '/login',
    component: login,
    name: 'login',
    meta: { requiresAuth: false },
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

router.beforeEach((to, _from, next) => {
  const userStore = useUserStore();
  if (to.name === 'login') {
    if (userStore.getCode()) {
      next({ path: '/' });
    } else {
      next();
    }
    return;
  }

  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth);

  if (requiresAuth && !userStore.getCode()) {
    next({
      path: '/login',
      query: { redirect: to.fullPath },
    });
  } else {
    next();
  }
});

export default router;
