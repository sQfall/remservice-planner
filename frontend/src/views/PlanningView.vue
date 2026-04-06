<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { usePlanningStore } from '@/stores/planning'
import { useBrigadesStore } from '@/stores/brigades'
import { useRequestsStore } from '@/stores/requests'

const planningStore = usePlanningStore()
const brigadesStore = useBrigadesStore()
const requestsStore = useRequestsStore()

const planDate = ref(new Date().toISOString().slice(0, 10))
const isPlanning = ref(false)
const errorMessage = ref(null)
const successMessage = ref(null)

const specializationLabels = {
  electrical: 'Электромонтаж',
  plumbing: 'Сантехника',
  hvac: 'Вентиляция',
  general: 'Универсальная',
}

const newRequestsCount = computed(() => {
  return requestsStore.items.filter((r) => r.status === 'new').length
})

const plannedCount = computed(() => {
  if (!planningStore.plan?.route_points) return 0
  return planningStore.plan.route_points.length
})

const totalHours = computed(() => {
  if (!planningStore.statistics?.length) return 0
  const totalMin = planningStore.statistics.reduce(
    (sum, s) => sum + (s.total_work_time_min || 0) + (s.overtime_minutes || 0),
    0
  )
  return (totalMin / 60).toFixed(1)
})

function clearMessages() {
  errorMessage.value = null
  successMessage.value = null
}

async function loadPlanForDate() {
  clearMessages()
  try {
    await planningStore.loadPlan(planDate.value)
    await planningStore.loadStatistics(planDate.value)
  } catch (e) {
    // план может не существовать
  }
}

watch(planDate, () => {
  loadPlanForDate()
})

async function runPlanning(useOrTools) {
  clearMessages()
  isPlanning.value = true
  try {
    await planningStore.runPlanning(planDate.value, useOrTools)
    await planningStore.loadStatistics(planDate.value)
    await requestsStore.loadRequests()

    const count = plannedCount.value
    if (count > 0) {
      successMessage.value = `План создан: ${count} заявок распределено по ${planningStore.statistics.length} бригадам`
    } else {
      errorMessage.value = 'Нет заявок со статусом "Новая" на выбранную дату'
    }
  } catch (e) {
    console.error('Ошибка планирования:', e)
    errorMessage.value = e.message || 'Не удалось создать план'
  } finally {
    isPlanning.value = false
  }
}

async function onReset() {
  if (!confirm('Удалить план и вернуть заявки в статус "Новая"?')) return
  clearMessages()
  try {
    await planningStore.resetPlan(planDate.value)
    planningStore.statistics = []
    await requestsStore.loadRequests()
    successMessage.value = 'План сброшен, заявки возвращены в статус "Новая"'
  } catch (e) {
    console.error('Ошибка сброса плана:', e)
    errorMessage.value = e.message || 'Не удалось сбросить план'
  }
}

onMounted(async () => {
  await brigadesStore.loadBrigades()
  await requestsStore.loadRequests()
  await loadPlanForDate()
})
</script>

<template>
  <div class="planning-view">
    <div v-if="errorMessage" class="error-banner">
      {{ errorMessage }}
      <button class="error-close" @click="errorMessage = null">✕</button>
    </div>

    <div v-if="successMessage" class="success-banner">
      {{ successMessage }}
      <button class="success-close" @click="successMessage = null">✕</button>
    </div>

    <div class="controls">
      <h1>Планирование</h1>
      <div class="controls-row">
        <input v-model="planDate" type="date" class="date-input" />
        <button class="btn-primary" :disabled="isPlanning" @click="runPlanning(false)">
          Быстрый план
        </button>
        <button class="btn-secondary" :disabled="isPlanning" @click="runPlanning(true)">
          Оптимальный план
        </button>
        <button class="btn-danger" :disabled="isPlanning" @click="onReset">
          Сбросить
        </button>
      </div>
      <p class="controls-hint">
        Быстрый - жадный алгоритм без учёта смены.
        Оптимальный - OR-Tools с учётом смены (+60 мин).
      </p>
    </div>

    <div v-if="isPlanning" class="loading-overlay">
      <div class="loading-spinner"></div>
      <span>Планирование выполняется...</span>
    </div>

    <div class="stats-row">
      <div class="stat-tile">
        <div class="stat-value">{{ newRequestsCount }}</div>
        <div class="stat-label">Новых заявок</div>
      </div>
      <div class="stat-tile">
        <div class="stat-value">{{ plannedCount }}</div>
        <div class="stat-label">Запланировано</div>
      </div>
      <div class="stat-tile">
        <div class="stat-value">{{ planningStore.statistics.length || 0 }}</div>
        <div class="stat-label">Бригад</div>
      </div>
      <div class="stat-tile">
        <div class="stat-value">{{ totalHours }}</div>
        <div class="stat-label">Всего часов</div>
      </div>
    </div>

    <div v-if="planningStore.statistics.length" class="brigades-table-section">
      <table class="data-table">
        <thead>
          <tr>
            <th>Бригада</th>
            <th>Специализация</th>
            <th>Заявок</th>
            <th>Время работы</th>
            <th>Овертайм</th>
            <th>Переездов, км</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="stat in planningStore.statistics" :key="stat.brigade_id">
            <td>{{ brigadesStore.byId(stat.brigade_id)?.name || stat.brigade_id }}</td>
            <td>
              {{ specializationLabels[brigadesStore.byId(stat.brigade_id)?.specialization] || '-' }}
            </td>
            <td>{{ stat.total_requests }}</td>
            <td>{{ stat.total_work_time_min }} мин</td>
            <td :class="{ 'overtime-warn': stat.overtime_minutes > 0 }">
              {{ stat.overtime_minutes > 0 ? stat.overtime_minutes + ' мин' : '-' }}
            </td>
            <td>{{ stat.total_distance_km.toFixed(1) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else-if="!isPlanning" class="empty-state">
      Выберите дату и нажмите "Быстрый план" или "Оптимальный план"
    </div>
  </div>
</template>

<style scoped>
.planning-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.controls h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 0.75rem;
}

.controls-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.date-input {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 0.9rem;
  background: var(--color-surface);
  color: var(--color-text);
}

.date-input:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-accent-light);
}

.controls-hint {
  font-size: 0.85rem;
  color: var(--color-text-secondary);
  margin-top: 0.4rem;
}

.loading-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 1.5rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  color: var(--color-text-secondary);
  font-size: 0.95rem;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-banner,
.success-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-radius: var(--radius);
  font-size: 0.9rem;
}

.error-banner {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.success-banner {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
}

.error-close,
.success-close {
  background: none;
  border: none;
  font-size: 1rem;
  cursor: pointer;
  padding: 0 0.25rem;
  line-height: 1;
  opacity: 0.6;
}

.error-close:hover,
.success-close:hover {
  opacity: 1;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
}

@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stat-tile {
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1rem;
  text-align: center;
  background: var(--color-surface);
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--color-text);
  line-height: 1.2;
}

.stat-label {
  font-size: 0.8rem;
  color: var(--color-text-secondary);
  margin-top: 0.25rem;
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

.overtime-warn {
  color: var(--color-danger);
  font-weight: 600;
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--color-text-secondary);
}
</style>
