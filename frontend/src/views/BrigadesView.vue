<script setup>
import { onMounted } from 'vue'
import { useBrigadesStore } from '@/stores/brigades'

const store = useBrigadesStore()

const specializationLabels = {
  electrical: 'Электромонтаж',
  plumbing: 'Сантехника',
  hvac: 'Вентиляция',
  general: 'Универсальная',
}

const specializationClass = (spec) => `spec-badge spec-${spec}`

onMounted(() => {
  store.loadBrigades()
})

function formatInitials(name) {
  const parts = name.trim().split(' ')
  if (parts.length >= 3) {
    return `${parts[0]} ${parts[1][0]}.${parts[2][0]}.`
  }
  if (parts.length === 2) {
    return `${parts[0]} ${parts[1][0]}.`
  }
  return name
}
</script>

<template>
  <div class="brigades-view">
    <h1>Бригады</h1>

    <div v-if="store.loading" class="loading-text">Загрузка...</div>

    <div v-else-if="store.items.length" class="brigades-grid">
      <div v-for="brigade in store.items" :key="brigade.id" class="brigade-card">
        <div class="card-header">
          <span class="brigade-name">{{ brigade.name }}</span>
          <span :class="specializationClass(brigade.specialization)">
            {{ specializationLabels[brigade.specialization] || brigade.specialization }}
          </span>
        </div>

        <div class="card-body">
          <div class="info-row">Смена: {{ brigade.shift_start }} - {{ brigade.shift_end }}</div>
          <div v-if="brigade.vehicles?.length" class="info-row">
            Автомобиль: {{ brigade.vehicles[0].plate }} | Тип: {{ brigade.vehicles[0].vehicle_type }}
          </div>
          <div v-else class="info-row">Автомобиль: не назначен</div>
        </div>

        <hr class="card-divider" />

        <div class="members-list">
          <div v-for="member in brigade.members" :key="member.id" class="member-row">
            {{ formatInitials(member.full_name) }} - {{ member.role }}
          </div>
          <div v-if="!brigade.members?.length" class="member-row">Состав не указан</div>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">Бригад не найдено</div>
  </div>
</template>

<style scoped>
.brigades-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.brigades-view h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text);
}

.brigades-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

@media (max-width: 900px) {
  .brigades-grid {
    grid-template-columns: 1fr;
  }
}

.brigade-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.brigade-name {
  font-weight: 700;
  font-size: 1.05rem;
  color: var(--color-text);
}

.spec-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
  font-size: 0.75rem;
  font-weight: 500;
  white-space: nowrap;
}

.spec-electrical {
  background: rgba(59, 130, 246, 0.1);
  color: #1d4ed8;
}

.spec-plumbing {
  background: rgba(20, 184, 166, 0.1);
  color: #0f766e;
}

.spec-hvac {
  background: rgba(139, 92, 246, 0.1);
  color: #6d28d9;
}

.spec-general {
  background: rgba(100, 116, 139, 0.1);
  color: #475569;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.75rem;
}

.info-row {
  font-size: 0.9rem;
  color: var(--color-text-secondary);
}

.card-divider {
  border: none;
  border-top: 1px solid var(--color-border);
  margin: 0 0 0.75rem;
}

.members-list {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.member-row {
  font-size: 0.9rem;
  color: var(--color-text);
}

.loading-text {
  text-align: center;
  padding: 2rem;
  color: var(--color-text-secondary);
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--color-text-secondary);
}
</style>
