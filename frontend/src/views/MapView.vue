<script setup>
import { ref, onMounted } from 'vue'
import MapComponent from '@/components/MapComponent.vue'
import { usePlanningStore } from '@/stores/planning'

const planningStore = usePlanningStore()

const selectedDate = ref(new Date().toISOString().slice(0, 10))
const selectedBrigadeId = ref(null)

async function loadGeometry() {
  try {
    await planningStore.loadGeometry(selectedDate.value)
  } catch (e) {
    // план может не существовать
  }
}

onMounted(async () => {
  await loadGeometry()
})
</script>

<template>
  <div class="map-view">
    <div class="map-controls">
      <label for="map-date">Дата плана:</label>
      <input id="map-date" v-model="selectedDate" type="date" @change="loadGeometry" />
      <select v-model="selectedBrigadeId">
        <option :value="null">Все бригады</option>
      </select>
    </div>

    <MapComponent
      :routes-geometry="planningStore.routesGeometry"
      :selected-brigade-id="selectedBrigadeId"
    />

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

.map-controls {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.map-controls label {
  font-size: 0.9rem;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.map-controls input,
.map-controls select {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 0.9rem;
  background: var(--color-surface);
  color: var(--color-text);
}

.map-controls input:focus,
.map-controls select:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-accent-light);
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
