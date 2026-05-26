import type { RouteRecordRaw } from 'vue-router'

export const AppRoutes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@views/LoginView.vue'),
    meta: { layout: 'blank', public: true }
  },
  {
    path: '/',
    component: () => import('@layout/MainLayout.vue'),
    redirect: '/chat',
    children: [
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@views/ChatView.vue'),
        meta: { title: '对话' }
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@views/TasksView.vue'),
        meta: { title: '任务' }
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@views/KnowledgeView.vue'),
        meta: { title: '知识库' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@views/SettingsView.vue'),
        meta: { title: '设置' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/chat'
  }
]
