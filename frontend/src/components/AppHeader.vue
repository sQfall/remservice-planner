<script setup>
import { RouterLink } from 'vue-router'
</script>

<template>
  <header class="app-header">
    <RouterLink to="/" class="header-brand">
      РемСервис
    </RouterLink>
    <nav class="header-nav">
      <RouterLink to="/" class="nav-link">Заявки</RouterLink>
      <RouterLink to="/brigades" class="nav-link">Бригады</RouterLink>
      <RouterLink to="/planning" class="nav-link">Планирование</RouterLink>
      <RouterLink to="/map" class="nav-link">Карта</RouterLink>
      <RouterLink to="/route-sheets" class="nav-link">Маршрутные листы</RouterLink>
    </nav>
  </header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 0.75rem 1.5rem;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
}

.header-brand {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--color-text);
  text-decoration: none;
  letter-spacing: -0.01em;
}

.header-brand:hover {
  text-decoration: none;
  color: var(--color-accent);
}

.header-nav {
  display: flex;
  gap: 1.5rem;
  align-items: center;
}

.nav-link {
  font-size: 0.95rem;
  color: var(--color-text-secondary);
  text-decoration: none;
  padding: 0.25rem 0;
  border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}

.nav-link:hover {
  color: var(--color-text);
  text-decoration: none;
}

.nav-link.router-link-active {
  color: var(--color-accent);
  border-bottom-color: var(--color-accent);
}
</style>
