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
      {
        path: 'aura/profiles',
        name: 'auraUserProfiles',
        component: () => import('@/pages/aura/UserProfiles.vue'),
        meta: { title: '用户画像' },
      },
      {
        path: 'aura/personas',
        name: 'auraPersonaConfigs',
        component: () => import('@/pages/aura/PersonaConfigs.vue'),
        meta: { title: '人设配置' },
      },
      {
        path: 'aura/relationships',
        name: 'auraRelationshipStates',
        component: () => import('@/pages/aura/RelationshipStates.vue'),
        meta: { title: '关系状态' },
      },
      {
        path: 'aura/messages',
        name: 'auraSessionMessages',
        component: () => import('@/pages/aura/SessionMessages.vue'),
        meta: { title: '会话消息' },
      },
      {
        path: 'aura/emotions',
        name: 'auraEmotionSnapshots',
        component: () => import('@/pages/aura/EmotionSnapshots.vue'),
        meta: { title: '情绪快照' },
      },
      {
        path: 'aura/memories',
        name: 'auraLongTermMemories',
        component: () => import('@/pages/aura/LongTermMemories.vue'),
        meta: { title: '长期记忆列表' },
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
