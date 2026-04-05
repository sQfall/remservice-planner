<script setup>
import AppHeader from '@/components/AppHeader.vue'
</script>

<template>
  <div class="app-layout">
    <AppHeader />
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  --color-bg: #f8fafc;
  --color-surface: #ffffff;
  --color-text: #0f172a;
  --color-text-secondary: #475569;
  --color-border: #e2e8f0;
  --color-border-hover: #cbd5e1;
  --color-accent: #3b82f6;
  --color-accent-hover: #2563eb;
  --color-accent-light: #dbeafe;
  --color-success: #22c55e;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
  --color-danger-hover: #dc2626;
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --radius: 6px;
  --font-sans: Inter, system-ui, -apple-system, sans-serif;
}

html {
  font-size: 14px;
  line-height: 1.5;
}

body {
  font-family: var(--font-sans);
  background: var(--color-bg);
  color: var(--color-text);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-main {
  flex: 1;
  padding: 1.5rem;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
}

a {
  color: var(--color-accent);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

button {
  font-family: var(--font-sans);
  cursor: pointer;
}

input,
select,
textarea {
  font-family: var(--font-sans);
  font-size: 1rem;
}

table {
  border-collapse: collapse;
  width: 100%;
}
</style>
