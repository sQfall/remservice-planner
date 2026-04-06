<script setup>
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useRequestsStore } from '@/stores/requests'

const router = useRouter()
const store = useRequestsStore()

const statusLabels = {
  new: 'Новая',
  planned: 'Запланирована',
  in_progress: 'В работе',
  completed: 'Выполнена',
  cancelled: 'Отменена',
}

const workTypeLabels = {
  electrical: 'Электромонтаж',
  plumbing: 'Сантехника',
  hvac: 'Вентиляция',
  structural: 'Строительные',
  general: 'Общие',
}

const priorityLabels = {
  emergency: 'Аварийный',
  high: 'Высокий',
  medium: 'Обычный',
  low: 'Низкий',
}

const priorityClass = (priority) => `badge-priority badge-priority-${priority}`
const statusClass = (status) => `badge-status badge-status-${status}`

const availableDates = computed(() => {
  const dates = new Set()
  store.items.forEach((r) => {
    if (r.planned_at) {
      dates.add(r.planned_at.slice(0, 10))
    }
  })
  return Array.from(dates).sort().reverse()
})

function formatDate(dateStr) {
  const [y, m, d] = dateStr.split('-')
  return `${d}.${m}.${y}`
}

function onFilterChange() {
  store.loadRequests()
}

function resetFilters() {
  store.filters.date = null
  store.filters.status = null
  store.filters.work_type = null
  store.filters.priority = null
  store.loadRequests()
}

async function onDelete(id) {
  if (!confirm('Удалить заявку?')) return
  try {
    await store.deleteRequest(id)
  } catch (e) {
    // ошибка уже залогирована в interceptor
  }
}
</script>

<template>
  <div class="requests-view">
    <div class="view-header">
      <h1>Заявки</h1>
      <button class="btn-primary" @click="router.push('/requests/new')">Создать заявку</button>
    </div>

    <div class="filters">
      <select v-model="store.filters.date" @change="onFilterChange">
        <option :value="null">Все даты</option>
        <option v-for="d in availableDates" :key="d" :value="d">{{ formatDate(d) }}</option>
      </select>
      <select v-model="store.filters.status" @change="onFilterChange">
        <option :value="null">Все статусы</option>
        <option v-for="(label, key) in statusLabels" :key="key" :value="key">{{ label }}</option>
      </select>
      <select v-model="store.filters.work_type" @change="onFilterChange">
        <option :value="null">Все типы</option>
        <option v-for="(label, key) in workTypeLabels" :key="key" :value="key">{{ label }}</option>
      </select>
      <select v-model="store.filters.priority" @change="onFilterChange">
        <option :value="null">Все приоритеты</option>
        <option v-for="(label, key) in priorityLabels" :key="key" :value="key">{{ label }}</option>
      </select>
      <button class="btn-secondary" @click="resetFilters">Сбросить</button>
    </div>

    <div v-if="store.loading" class="loading-text">Загрузка...</div>

    <table v-else-if="store.filteredItems.length" class="data-table">
      <thead>
        <tr>
          <th>№</th>
          <th>Клиент</th>
          <th>Адрес</th>
          <th>Тип работ</th>
          <th>Приоритет</th>
          <th>Статус</th>
          <th>Дата</th>
          <th>Бригада</th>
          <th>Действия</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="req in store.filteredItems" :key="req.id">
          <td>{{ req.id }}</td>
          <td>{{ req.contact_person || '—' }}</td>
          <td>{{ req.address }}</td>
          <td>{{ workTypeLabels[req.work_type] || req.work_type }}</td>
          <td>
            <span :class="priorityClass(req.priority)">
              {{ priorityLabels[req.priority] || req.priority }}
            </span>
          </td>
          <td>
            <span :class="statusClass(req.status)">
              {{ statusLabels[req.status] || req.status }}
            </span>
          </td>
          <td>{{ req.planned_at ? new Date(req.planned_at).toLocaleDateString('ru-RU') : '—' }}</td>
          <td>{{ req.brigade?.name || '—' }}</td>
          <td class="actions-cell">
            <button class="btn-secondary btn-sm" @click="router.push(`/requests/${req.id}/edit`)">Изм.</button>
            <button class="btn-danger btn-sm" @click="onDelete(req.id)">Удал.</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-else class="empty-state">Заявок не найдено</div>
  </div>
</template>

<style scoped>
.requests-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.view-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text);
}

.filters {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.filters select {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-surface);
  color: var(--color-text);
  font-size: 0.9rem;
  min-width: 140px;
}

.filters select:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-accent-light);
}

.data-table {
  background: var(--color-surface);
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
}

.data-table th,
.data-table td {
  padding: 0.6rem 0.75rem;
  text-align: left;
  font-size: 0.9rem;
}

.data-table thead th {
  background: #f1f5f9;
  font-weight: 600;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}

.data-table tbody tr {
  border-bottom: 1px solid var(--color-border);
}

.data-table tbody tr:last-child {
  border-bottom: none;
}

.data-table tbody tr:hover {
  background: #f8fafc;
}

.actions-cell {
  display: flex;
  gap: 0.4rem;
}

.badge-priority {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
  font-size: 0.8rem;
  font-weight: 500;
  white-space: nowrap;
}

.badge-priority-emergency {
  background: #fee2e2;
  color: #991b1b;
}

.badge-priority-high {
  background: #ffedd5;
  color: #9a3412;
}

.badge-priority-medium {
  background: #dbeafe;
  color: #1e40af;
}

.badge-priority-low {
  background: #f1f5f9;
  color: #475569;
}

.badge-status {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
  font-size: 0.8rem;
  font-weight: 500;
  white-space: nowrap;
}

.badge-status-new {
  background: #f1f5f9;
  color: #475569;
}

.badge-status-planned {
  background: #dbeafe;
  color: #1e40af;
}

.badge-status-in_progress {
  background: #fef3c7;
  color: #92400e;
}

.badge-status-completed {
  background: #dcfce7;
  color: #166534;
}

.badge-status-cancelled {
  background: #f1f5f9;
  color: #64748b;
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--color-text-secondary);
  font-size: 1rem;
}

.loading-text {
  text-align: center;
  padding: 2rem;
  color: var(--color-text-secondary);
}
</style>
