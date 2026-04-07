<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import MapComponent from '@/components/MapComponent.vue'
import { usePlanningStore } from '@/stores/planning'
import { useBrigadesStore } from '@/stores/brigades'

const planningStore = usePlanningStore()
const brigadesStore = useBrigadesStore()

const selectedDate = ref(new Date().toISOString().slice(0, 10))
const selectedBrigadeId = ref(null)

const BRIGADE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']

// Уникальные бригады из geometry
const legendBrigades = computed(() => {
  const features = planningStore.routesGeometry?.features || []
  const seen = new Set()
  features.forEach((f) => {
    const bid = f.properties?.brigade_id
    if (bid !== undefined) seen.add(bid)
  })
  
  // Берем имена и цвета из загруженного списка бригад (более надежно)
  return brigadesStore.items
    .filter((b) => seen.has(b.id))
    .map((b, index) => ({
      id: b.id,
      name: b.name,
      color: BRIGADE_COLORS[index % BRIGADE_COLORS.length],
    }))
})

// Select options из legendBrigades
const brigadeOptions = computed(() => {
  const allOption = { id: null, name: 'Все бригады' }
  return [allOption, ...legendBrigades.value]
})

async function loadGeometry() {
  try {
    await planningStore.loadGeometry(selectedDate.value)
  } catch (e) {
    planningStore.routesGeometry = null
  }
}

// При загрузке новой геометрии — сбросить фильтр
watch(
  () => planningStore.routesGeometry,
  () => {
    selectedBrigadeId.value = null
  }
)

onMounted(async () => {
  await brigadesStore.loadBrigades()
  // Маршруты больше не загружаются автоматически — только по кнопке
})
</script>

<template>
  <div class="map-view">
    <h1>Маршруты</h1>

    <div class="controls">
      <label for="map-date">Дата плана:</label>
      <input id="map-date" v-model="selectedDate" type="date" />
      <button class="btn-primary" @click="loadGeometry">Загрузить маршруты</button>

      <select v-model="selectedBrigadeId">
        <option v-for="opt in brigadeOptions" :key="opt.id" :value="opt.id">
          {{ opt.name }}
        </option>
      </select>
    </div>

    <div class="map-wrapper">
      <MapComponent
        :routes-geometry="planningStore.routesGeometry"
        :selected-brigade-id="selectedBrigadeId"
      />
    </div>

    <div v-if="legendBrigades.length" class="legend">
      <div v-for="b in legendBrigades" :key="b.id" class="legend-item">
        <span class="legend-dot" :style="{ background: b.color }"></span>
        <span class="legend-label">{{ b.name }}</span>
      </div>
    </div>

    <div v-if="!planningStore.routesGeometry?.features?.length" class="map-hint">
      Сначала создайте план на странице планирования
    </div>
  </div>
</template>

<style scoped>
.map-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.map-view h1 {
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

.controls label {
  font-size: 0.9rem;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.controls input,
.controls select {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 0.9rem;
  background: var(--color-surface);
  color: var(--color-text);
}

.controls input:focus,
.controls select:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-accent-light);
}

.map-wrapper {
  height: calc(100vh - 180px);
  min-height: 400px;
  border-radius: var(--radius);
  overflow: hidden;
}

.legend {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  padding: 0.75rem 1rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1px solid #fff;
  box-shadow: 0 0 0 1px var(--color-border);
}

.legend-label {
  font-size: 0.9rem;
  color: var(--color-text);
}

.map-hint {
  text-align: center;
  padding: 1rem;
  color: var(--color-text-secondary);
  font-size: 0.9rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}
</style>
