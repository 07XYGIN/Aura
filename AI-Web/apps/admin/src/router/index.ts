import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/pages/layout/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'home',
        component: () => import('@/pages/home/Home.vue'),
        meta: { title: '首页' },
      },
      {
        path: 'user/userInfo',
        name: 'userInfo',
        component: () => import('@/pages/user/UserInfo.vue'),
        meta: { title: '个人中心' },
      },
      {
        path: 'memory',
        name: 'memoryManage',
        component: () => import('@/pages/memory/MemoryManage.vue'),
        meta: { title: '记忆管理' },
      },
    ],
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/login/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/pages/register/Register.vue'),
    meta: { requiresAuth: false },
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')

  if (token && to.path === '/login') {
    return { path: '/' }
  }

  if (to.meta.requiresAuth && !token) {
    return { path: '/login' }
  }

  return true
})

export default router
