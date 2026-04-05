import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/views/RequestsView.vue'),
    meta: { title: 'Заявки' },
  },
  {
    path: '/brigades',
    component: () => import('@/views/BrigadesView.vue'),
    meta: { title: 'Бригады' },
  },
  {
    path: '/requests/new',
    component: () => import('@/views/RequestFormView.vue'),
    meta: { title: 'Новая заявка' },
  },
  {
    path: '/requests/:id/edit',
    component: () => import('@/views/RequestFormView.vue'),
    meta: { title: 'Редактировать заявку' },
  },
  {
    path: '/planning',
    component: () => import('@/views/PlanningView.vue'),
    meta: { title: 'Планирование' },
  },
  {
    path: '/map',
    component: () => import('@/views/MapView.vue'),
    meta: { title: 'Карта' },
  },
  {
    path: '/route-sheets',
    component: () => import('@/views/RouteSheetsView.vue'),
    meta: { title: 'Маршрутные листы' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} | РемСервис-Планировщик`
  }
})

export default router
