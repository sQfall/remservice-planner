<script setup>
import { RouterLink, useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()

const navItems = [
  { path: '/', label: 'Заявки' },
  { path: '/brigades', label: 'Бригады' },
  { path: '/planning', label: 'Планирование' },
  { path: '/map', label: 'Карта' },
  { path: '/route-sheets', label: 'Маршрутные листы' },
]

const isActive = computed(() => (path) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
})
</script>

<template>
  <header class="app-header">
    <RouterLink to="/" class="header-brand">
      <span class="brand-bold">РемСервис</span> <span class="brand-normal">Планировщик</span>
    </RouterLink>
    <nav class="header-nav">
      <RouterLink
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-link"
        :class="{ active: isActive(item.path) }"
      >
        {{ item.label }}
      </RouterLink>
    </nav>
  </header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 1.5rem;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  gap: 2rem;
}

.header-brand {
  text-decoration: none;
  white-space: nowrap;
  color: #0f172a;
}

.brand-bold {
  font-weight: 700;
}

.brand-normal {
  font-weight: 400;
}

.header-nav {
  display: flex;
  gap: 1.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.nav-link {
  font-size: 0.95rem;
  color: #475569;
  text-decoration: none;
  padding: 0.15rem 0;
  border-bottom: 2px solid transparent;
  transition: color 0.15s;
  white-space: nowrap;
}

.nav-link:hover {
  color: #3b82f6;
  text-decoration: none;
}

.nav-link.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

@media (max-width: 768px) {
  .app-header {
    height: auto;
    flex-direction: column;
    align-items: flex-start;
    padding: 0.75rem 1.5rem;
    gap: 0.5rem;
  }

  .header-nav {
    gap: 1rem;
  }
}
</style>
