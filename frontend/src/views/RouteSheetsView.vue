<script setup>
import { ref, computed, onMounted } from 'vue'
import { usePlanningStore } from '@/stores/planning'
import { fetchRouteSheets, downloadRoutePdf, issueRouteSheets } from '@/api'

const planningStore = usePlanningStore()

const selectedDate = ref(new Date().toISOString().slice(0, 10))
const routeSheets = ref([])
const loading = ref(false)
const issuing = ref(false)
const planStatus = ref(null) // Хранит статус плана: 'draft', 'confirmed', 'active'

const isIssued = computed(() => planStatus.value === 'active')

const workTypeLabels = {
  electrical: 'Электромонтаж',
  plumbing: 'Сантехника',
  hvac: 'Вентиляция',
  general: 'Общие',
}

function formatTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

async function loadSheets() {
  loading.value = true
  try {
    const data = await fetchRouteSheets(selectedDate.value)
    // Ищем объект со статусом плана (добавляется бэкендом)
    const statusObj = data.find(item => item._plan_status)
    planStatus.value = statusObj ? statusObj._plan_status : null
    // Убираем служебный объект из списка бригад
    routeSheets.value = data.filter(item => !item._plan_status)
  } catch (e) {
    routeSheets.value = []
    planStatus.value = null
  } finally {
    loading.value = false
  }
}

async function onIssue() {
  issuing.value = true
  try {
    await issueRouteSheets(selectedDate.value)
    await loadSheets()
  } catch (e) {
    // ошибка залогирована
  } finally {
    issuing.value = false
  }
}

async function downloadPdf(brigadeId) {
  try {
    const blob = await downloadRoutePdf(selectedDate.value, brigadeId)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `route_sheet_${brigadeId}_${selectedDate.value}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('Ошибка скачивания PDF:', e)
  }
}

onMounted(async () => {
  await loadSheets()
})
</script>

<template>
  <div class="route-sheets-view">
    <h1>Маршрутные листы</h1>

    <div class="controls">
      <input v-model="selectedDate" type="date" class="date-input" />
      <button class="btn-primary" :disabled="loading" @click="loadSheets">
        {{ loading ? 'Загрузка...' : 'Загрузить' }}
      </button>
      <button
        v-if="!isIssued"
        class="btn-secondary"
        :disabled="issuing || !routeSheets.length"
        @click="onIssue"
      >
        {{ issuing ? 'Выдача...' : 'Выдать листы' }}
      </button>
    </div>

    <div v-if="isIssued" class="issued-banner">
      ✓ Маршрутные листы на выбранную дату выданы
    </div>

    <div v-if="loading" class="loading-text">Загрузка...</div>

    <div v-else-if="routeSheets.length" class="brigades-list">
      <details v-for="sheet in routeSheets" :key="sheet.brigade_id" class="brigade-detail">
        <summary class="brigade-summary">
          <span class="summary-name">{{ sheet.brigade_name }}</span>
          <span class="summary-count">{{ sheet.route_points.length }} заявок</span>
          <span class="summary-vehicle" v-if="sheet.vehicle_plate">{{ sheet.vehicle_plate }}</span>
        </summary>

        <div class="detail-content">
          <table class="route-table">
            <thead>
              <tr>
                <th>№</th>
                <th>Время</th>
                <th>Адрес</th>
                <th>Клиент</th>
                <th>Телефон</th>
                <th>Вид работ</th>
                <th>Длительность</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="point in sheet.route_points" :key="point.sequence">
                <td>{{ point.sequence }}</td>
                <td>{{ formatTime(point.arrival_time) }}</td>
                <td>{{ point.request?.address || point.address }}</td>
                <td>{{ point.request?.contact_person || point.contact_person || '-' }}</td>
                <td>{{ point.request?.phone || point.phone || '-' }}</td>
                <td>{{ workTypeLabels[point.request?.work_type] || point.request?.work_type || '-' }}</td>
                <td>{{ point.request?.estimated_duration || '-' }} мин</td>
              </tr>
            </tbody>
          </table>

          <div class="detail-actions">
            <button class="btn-secondary" @click="downloadPdf(sheet.brigade_id)">Скачать PDF</button>
          </div>
        </div>
      </details>
    </div>

    <div v-else class="empty-state">
      Маршрутных листов на выбранную дату не найдено
    </div>
  </div>
</template>

<style scoped>
.route-sheets-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.route-sheets-view h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text);
}

.controls {
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

.loading-text {
  text-align: center;
  padding: 2rem;
  color: var(--color-text-secondary);
}

.brigades-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.brigade-detail {
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-surface);
}

.brigade-summary {
  display: flex;
  gap: 1rem;
  align-items: center;
  padding: 0.75rem 1rem;
  cursor: pointer;
  list-style: none;
  font-size: 0.95rem;
  color: var(--color-text);
}

.brigade-summary::-webkit-details-marker {
  display: none;
}

.brigade-summary::before {
  content: '>';
  display: inline-block;
  width: 1rem;
  transition: transform 0.15s;
  color: var(--color-text-secondary);
}

.brigade-detail[open] > .brigade-summary::before {
  transform: rotate(90deg);
}

.summary-name {
  font-weight: 600;
}

.summary-count {
  color: var(--color-text-secondary);
}

.summary-vehicle {
  color: var(--color-text-secondary);
  font-size: 0.85rem;
}

.detail-content {
  padding: 0 1rem 1rem;
}

.route-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.route-table th,
.route-table td {
  padding: 0.5rem 0.6rem;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
}

.route-table thead th {
  background: #f1f5f9;
  font-weight: 600;
  color: var(--color-text-secondary);
}

.route-table tbody tr:last-child td {
  border-bottom: none;
}

.route-table tbody tr:hover {
  background: #f8fafc;
}

.detail-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.75rem;
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--color-text-secondary);
}

.issued-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: #ecfdf5;
  border: 1px solid #6ee7b7;
  border-radius: var(--radius);
  color: #065f46;
  font-size: 0.9rem;
  font-weight: 500;
}
</style>
