<script setup>
import { ref, computed, onMounted } from 'vue'
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
})

const errors = ref({})
const geocoding = ref(false)

const workTypeOptions = [
  { value: 'electrical', label: 'Электромонтаж' },
  { value: 'plumbing', label: 'Сантехника' },
  { value: 'hvac', label: 'Отопление' },
  { value: 'structural', label: 'Строительные' },
  { value: 'general', label: 'Общие' },
]

const priorityOptions = [
  { value: 'low', label: 'Низкий' },
  { value: 'medium', label: 'Обычный' },
  { value: 'high', label: 'Высокий' },
  { value: 'emergency', label: 'Аварийный' },
]

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
      }
    } catch (e) {
      router.push('/')
    }
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
            :class="{ 'input-error': errors.address }"
          />
          <button
            type="button"
            class="btn-secondary"
            :disabled="geocoding || !form.address.trim()"
            @click="geocode"
          >
            {{ geocoding ? 'Определяю...' : 'Определить координаты' }}
          </button>
        </div>
        <span v-if="errors.address" class="error-text">{{ errors.address }}</span>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label for="latitude">Широта</label>
          <input id="latitude" v-model="form.latitude" type="number" step="any" readonly />
        </div>
        <div class="form-group">
          <label for="longitude">Долгота</label>
          <input id="longitude" v-model="form.longitude" type="number" step="any" readonly />
        </div>
      </div>

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
