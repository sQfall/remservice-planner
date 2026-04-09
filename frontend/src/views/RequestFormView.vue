<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useRequestsStore } from '@/stores/requests'

const router = useRouter()
const route = useRoute()
const store = useRequestsStore()

const isEdit = computed(() => !!route.params.id)

const form = ref({
  contact_person: '',
  phone: '',
  address: '',
  latitude: 0,
  longitude: 0,
  work_type: 'general',
  description: '',
  planned_at: '',
  estimated_duration: 60,
  priority: 'medium',
  time_window_start: '',
  time_window_end: '',
})

const errors = ref({})
const geocoding = ref(false)
const mapContainer = ref(null)

let map = null
let L = null
let marker = null
let tileLayer = null

const workTypeOptions = [
  { value: 'electrical', label: 'Электромонтаж' },
  { value: 'plumbing', label: 'Сантехника' },
  { value: 'hvac', label: 'Вентиляция и кондиционирование' },
  { value: 'general', label: 'Общие работы' },
]

const priorityOptions = [
  { value: 'low', label: 'Низкий' },
  { value: 'medium', label: 'Обычный' },
  { value: 'high', label: 'Высокий' },
  { value: 'emergency', label: 'Аварийный' },
]

async function initMap() {
  L = await import('leaflet')
  await import('leaflet/dist/leaflet.css')

  const defaultLat = form.value.latitude || 55.75
  const defaultLng = form.value.longitude || 37.62
  const zoom = form.value.latitude ? 15 : 10

  map = L.map(mapContainer.value).setView([defaultLat, defaultLng], zoom)

  tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 18,
  }).addTo(map)

  // Если есть координаты — ставим маркер
  if (form.value.latitude && form.value.longitude) {
    setMarker(form.value.latitude, form.value.longitude)
  }

  // Клик по карте
  map.on('click', onMapClick)

  // Перерисовка карты после рендера
  setTimeout(() => map.invalidateSize(), 100)
}

function onMapClick(e) {
  const { lat, lng } = e.latlng
  form.value.latitude = lat
  form.value.longitude = lng
  setMarker(lat, lng)
  reverseGeocode(lat, lng)
}

function setMarker(lat, lng) {
  if (marker) {
    marker.setLatLng([lat, lng])
  } else {
    // Фикс иконки маркера Leaflet
    delete L.Icon.Default.prototype._getIconUrl
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
      iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
      shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    })
    marker = L.marker([lat, lng], { draggable: true }).addTo(map)
    marker.on('dragend', onMarkerDragEnd)
  }
}

function onMarkerDragEnd(e) {
  const { lat, lng } = e.target.getLatLng()
  form.value.latitude = lat
  form.value.longitude = lng
  reverseGeocode(lat, lng)
}

async function reverseGeocode(lat, lng) {
  geocoding.value = true
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&countrycodes=ru`,
      { headers: { 'User-Agent': 'RemServicePlanner/1.0' } }
    )
    const data = await response.json()
    if (data && data.display_name) {
      form.value.address = data.display_name
    }
  } catch (e) {
    console.error('Ошибка обратного геокодирования:', e)
  } finally {
    geocoding.value = false
  }
}

onMounted(async () => {
  if (isEdit.value) {
    const id = parseInt(route.params.id)
    try {
      const data = await store.loadRequest(id)
      form.value = {
        contact_person: data.contact_person || '',
        phone: data.phone || '',
        address: data.address || '',
        latitude: data.latitude || 0,
        longitude: data.longitude || 0,
        work_type: data.work_type || 'general',
        description: data.description || '',
        planned_at: data.planned_at ? new Date(data.planned_at).toISOString().slice(0, 16) : '',
        estimated_duration: data.estimated_duration || 60,
        priority: data.priority || 'medium',
        time_window_start: data.time_window_start || '',
        time_window_end: data.time_window_end || '',
      }
    } catch (e) {
      router.push('/')
    }
  }

  await initMap()
})

onUnmounted(() => {
  if (map) {
    map.remove()
    map = null
  }
})

function validate() {
  errors.value = {}
  if (!form.value.contact_person.trim()) {
    errors.value.contact_person = 'ФИО обязательно'
  }
  if (!form.value.phone.trim()) {
    errors.value.phone = 'Телефон обязателен'
  }
  if (!form.value.address.trim()) {
    errors.value.address = 'Адрес обязателен'
  }
  if (!form.value.planned_at) {
    errors.value.planned_at = 'Укажите желаемую дату'
  }
  // Валидация временного окна: если одно заполнено — другое обязательно
  if (form.value.time_window_start || form.value.time_window_end) {
    if (!form.value.time_window_start) {
      errors.value.time_window_start = 'Укажите начало окна'
    }
    if (!form.value.time_window_end) {
      errors.value.time_window_end = 'Укажите конец окна'
    }
    if (form.value.time_window_start && form.value.time_window_end &&
        form.value.time_window_start >= form.value.time_window_end) {
      errors.value.time_window_end = 'Конец окна должен быть позже начала'
    }
  }
  return Object.keys(errors.value).length === 0
}

async function geocode() {
  if (!form.value.address.trim()) return
  geocoding.value = true
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(form.value.address)}&format=json&limit=1&countrycodes=ru`,
      { headers: { 'User-Agent': 'RemServicePlanner/1.0' } }
    )
    const data = await response.json()
    if (data && data.length > 0) {
      form.value.latitude = parseFloat(data[0].lat)
      form.value.longitude = parseFloat(data[0].lon)
      setMarker(form.value.latitude, form.value.longitude)
      map.setView([form.value.latitude, form.value.longitude], 15)
    }
  } catch (e) {
    console.error('Ошибка геокодирования:', e)
  } finally {
    geocoding.value = false
  }
}

async function onSubmit() {
  if (!validate()) return

  const payload = {
    ...form.value,
    latitude: form.value.latitude || 0,
    longitude: form.value.longitude || 0,
    planned_at: form.value.planned_at ? new Date(form.value.planned_at).toISOString() : null,
    time_window_start: form.value.time_window_start || null,
    time_window_end: form.value.time_window_end || null,
  }

  try {
    if (isEdit.value) {
      await store.updateRequest(parseInt(route.params.id), payload)
    } else {
      await store.createRequest(payload)
    }
    router.push('/')
  } catch (e) {
    // ошибка залогирована
  }
}

function onCancel() {
  router.back()
}
</script>

<template>
  <div class="request-form-view">
    <h1>{{ isEdit ? 'Редактировать заявку' : 'Новая заявка' }}</h1>

    <form class="request-form" @submit.prevent="onSubmit">
      <div class="form-group">
        <label for="contact_person">ФИО клиента</label>
        <input
          id="contact_person"
          v-model="form.contact_person"
          type="text"
          required
          :class="{ 'input-error': errors.contact_person }"
        />
        <span v-if="errors.contact_person" class="error-text">{{ errors.contact_person }}</span>
      </div>

      <div class="form-group">
        <label for="phone">Телефон клиента</label>
        <input
          id="phone"
          v-model="form.phone"
          type="tel"
          required
          :class="{ 'input-error': errors.phone }"
        />
        <span v-if="errors.phone" class="error-text">{{ errors.phone }}</span>
      </div>

      <div class="form-group">
        <label for="address">Адрес</label>
        <div class="address-row">
          <input
            id="address"
            v-model="form.address"
            type="text"
            required
            placeholder="Введите адрес или выберите на карте"
            :class="{ 'input-error': errors.address }"
          />
          <button
            type="button"
            class="btn-secondary"
            :disabled="geocoding || !form.address.trim()"
            @click="geocode"
          >
            {{ geocoding ? 'Определяю...' : 'Найти' }}
          </button>
        </div>
        <span v-if="errors.address" class="error-text">{{ errors.address }}</span>
      </div>

      <div class="form-group">
        <label>Точка на карте</label>
        <p class="map-hint">Кликните по карте, чтобы установить координаты и определить адрес</p>
        <div ref="mapContainer" class="map-container"></div>
      </div>

      <input type="hidden" v-model="form.latitude" />
      <input type="hidden" v-model="form.longitude" />

      <div class="form-group">
        <label for="work_type">Тип работ</label>
        <select id="work_type" v-model="form.work_type">
          <option v-for="opt in workTypeOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>

      <div class="form-group">
        <label for="description">Описание работ</label>
        <textarea id="description" v-model="form.description" rows="3"></textarea>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label for="planned_at">Желаемая дата</label>
          <input
            id="planned_at"
            v-model="form.planned_at"
            type="date"
            required
            :class="{ 'input-error': errors.planned_at }"
          />
          <span v-if="errors.planned_at" class="error-text">{{ errors.planned_at }}</span>
        </div>
        <div class="form-group">
          <label for="estimated_duration">Длительность работ, мин</label>
          <input id="estimated_duration" v-model.number="form.estimated_duration" type="number" min="1" />
        </div>
      </div>

      <div class="form-group">
        <label>Временное окно визита</label>
        <p class="window-hint">Необязательно. Если заполнено — бригада прибудет в указанный интервал.</p>
        <div class="form-row">
          <div class="form-group">
            <label for="time_window_start">Начало окна</label>
            <input
              id="time_window_start"
              v-model="form.time_window_start"
              type="time"
              :class="{ 'input-error': errors.time_window_start }"
            />
            <span v-if="errors.time_window_start" class="error-text">{{ errors.time_window_start }}</span>
          </div>
          <div class="form-group">
            <label for="time_window_end">Конец окна</label>
            <input
              id="time_window_end"
              v-model="form.time_window_end"
              type="time"
              :class="{ 'input-error': errors.time_window_end }"
            />
            <span v-if="errors.time_window_end" class="error-text">{{ errors.time_window_end }}</span>
          </div>
        </div>
      </div>

      <div class="form-group">
        <label for="priority">Приоритет</label>
        <select id="priority" v-model="form.priority">
          <option v-for="opt in priorityOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>

      <div class="form-actions">
        <button type="submit" class="btn-primary">{{ isEdit ? 'Сохранить' : 'Создать заявку' }}</button>
        <button type="button" class="btn-secondary" @click="onCancel">Отмена</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.request-form-view {
  max-width: 600px;
  margin: 0 auto;
  padding: 0 1rem;
}

.request-form-view h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 1.25rem;
  color: var(--color-text);
}

.request-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.form-group label {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--color-text-secondary);
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 0.95rem;
  background: var(--color-surface);
  color: var(--color-text);
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-accent-light);
}

.form-group input:read-only {
  background: #f1f5f9;
  color: var(--color-text-secondary);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.address-row {
  display: flex;
  gap: 0.5rem;
}

.address-row input {
  flex: 1;
}

.address-row input::placeholder {
  color: var(--color-text-secondary);
  opacity: 0.6;
}

.map-container {
  width: 100%;
  height: 300px;
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
  z-index: 1;
}

.map-hint {
  font-size: 0.8rem;
  color: var(--color-text-secondary);
  margin: 0 0 0.4rem 0;
}

.window-hint {
  font-size: 0.8rem;
  color: var(--color-text-secondary);
  margin: 0 0 0.4rem 0;
}

.error-text {
  font-size: 0.8rem;
  color: var(--color-danger);
}

.input-error {
  border-color: var(--color-danger) !important;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.5rem;
}
</style>
