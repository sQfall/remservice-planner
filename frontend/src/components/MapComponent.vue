<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  routesGeometry: { type: Object, default: null },
  selectedBrigadeId: { type: Number, default: null },
})

const BRIGADE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']

const mapContainer = ref(null)

let map = null
let L = null
let tileLayer = null
let layersGroup = null

async function initMap() {
  L = await import('leaflet')
  import('leaflet/dist/leaflet.css')

  map = L.map(mapContainer.value).setView([55.75, 37.62], 10)

  tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 18,
  }).addTo(map)

  layersGroup = L.layerGroup().addTo(map)
}

function getBrigadeColor(index) {
  return BRIGADE_COLORS[index % BRIGADE_COLORS.length]
}

function drawGeometry(geometry) {
  if (!L || !layersGroup) return

  layersGroup.clearLayers()

  if (!geometry || !geometry.features || !geometry.features.length) return

  // Собираем уникальные бригады для определения цвета
  const brigadeIndices = {}
  let colourIndex = 0

  geometry.features.forEach((feature) => {
    const bid = feature.properties?.brigade_id
    if (bid !== undefined && !(bid in brigadeIndices)) {
      brigadeIndices[bid] = colourIndex++
    }
  })

  const pointSet = new Map() // Для fitBounds
  const brigadeRoutes = {} // Для хранения последовательности точек { brigadeId: [ "Гараж", "Адрес 1", ... ] }

  // 1. Сначала собираем точки для построения описания маршрутов
  geometry.features.forEach((feature) => {
    if (feature.geometry.type !== 'Point') return
    const props = feature.properties || {}
    const bid = props.brigade_id
    const type = props.type
    
    if (!brigadeRoutes[bid]) {
      brigadeRoutes[bid] = { points: [], name: props.brigade_name || `Бригада #${bid}` }
    }
    
    if (type === 'garage') {
      brigadeRoutes[bid].points.push('Гараж')
    } else if (type === 'request') {
      brigadeRoutes[bid].points.push(props.address || `Заявка #${props.request_id}`)
    }
  })

  // Формируем текстовое описание для каждой бригады
  const routeDescriptions = {}
  for (const [bid, data] of Object.entries(brigadeRoutes)) {
    // Гарантируем, что маршрут начинается и заканчивается гаражом, если есть точки
    if (data.points.length > 0) {
      if (data.points[0] !== 'Гараж') data.points.unshift('Гараж')
      if (data.points[data.points.length - 1] !== 'Гараж') data.points.push('Гараж')
      routeDescriptions[bid] = data.points.join(' → ')
    } else {
      routeDescriptions[bid] = `${data.name} (нет точек)`
    }
  }

  // 2. Рисуем линии
  geometry.features.forEach((feature) => {
    const props = feature.properties || {}
    const bid = props.brigade_id
    const brigadeIdx = brigadeIndices[bid] ?? 0
    const color = props.color || getBrigadeColor(brigadeIdx)

    // Обработка точек (Point)
    if (feature.geometry.type === 'Point') {
      const [lon, lat] = feature.geometry.coordinates
      const pointType = props.type // 'request' или 'garage'
      
      let marker
      if (pointType === 'garage') {
        // Маркер гаража — иконка домика или крупная точка
        marker = L.circleMarker([lat, lon], {
          radius: 12,
          fillColor: '#475569', // Серый цвет для гаража
          color: '#fff',
          weight: 2,
          fillOpacity: 1,
          dashArray: '2, 2', // Пунктирная обводка для отличия
        })
        const popupContent = `<b>Гараж</b><br>${props.brigade_name || 'Бригада #' + bid}`
        marker.bindPopup(popupContent)
      } else {
        // Маркер заявки — цветной круг
        marker = L.circleMarker([lat, lon], {
          radius: 8,
          fillColor: color,
          color: '#fff',
          weight: 2,
          fillOpacity: 0.9,
        })
        const popupContent = `<b>Заявка</b><br>${props.address || 'ID: ' + props.request_id}<br><span style="color:${color}">●</span> ${props.brigade_name || ''}`
        marker.bindPopup(popupContent)
      }
      marker.addTo(layersGroup)
      pointSet.set(`${lat.toFixed(6)},${lon.toFixed(6)}`, { lat, lon })
    }
    // Обработка линий (LineString)
    else if (feature.geometry.type === 'LineString') {
      const isGarage = props.is_garage_segment
      const latlngs = feature.geometry.coordinates.map(([lon, lat]) => [lat, lon])

      if (isGarage) {
        // Пунктир цвета бригады для сегментов от/до гаража
        const line = L.polyline(latlngs, {
          color: color,
          weight: 5,
          dashArray: '5, 8',
          opacity: 0.8,
        })
        line.addTo(layersGroup)
      } else {
        // Цветная сплошная линия для маршрутов
        const line = L.polyline(latlngs, {
          color: color,
          weight: 6,
          opacity: 0.9,
        })
        line.addTo(layersGroup)
        
        // Добавляем попап с описанием маршрута
        if (routeDescriptions[bid]) {
          line.bindPopup(`<b>${props.brigade_name || ''}</b><br>${routeDescriptions[bid]}`)
        }
      }

      // Собираем координаты для fitBounds
      latlngs.forEach(([lat, lon]) => {
        pointSet.set(`${lat.toFixed(6)},${lon.toFixed(6)}`, { lat, lon })
      })
    }
  })

  // Fit bounds
  if (pointSet.size > 0) {
    const bounds = [...pointSet.values()].map((p) => [p.lat, p.lon])
    map.fitBounds(bounds, { padding: [50, 50] })
  }
}

function highlightBrigade(brigadeId) {
  if (!layersGroup) return

  layersGroup.eachLayer((layer) => {
    if (!brigadeId) {
      // Показать все
      if (layer.setStyle) {
        layer.setStyle({ opacity: 0.85 })
      } else if (layer.setOpacity) {
        layer.setOpacity(1)
      }
      return
    }

    const popup = layer.getPopup?.()
    const content = popup?.getContent?.() || ''
    const belongs = content.includes(brigadeId) || layer.options?.color === getBrigadeColor(0)

    if (layer.setStyle) {
      layer.setStyle({ opacity: belongs ? 0.85 : 0.1 })
    }
  })
}

watch(
  () => props.routesGeometry,
  (geometry) => {
    if (geometry) {
      drawGeometry(geometry)
    } else if (layersGroup) {
      layersGroup.clearLayers()
    }
  }
)

watch(
  () => props.selectedBrigadeId,
  (id) => {
    highlightBrigade(id)
  }
)

onMounted(async () => {
  await initMap()
  if (props.routesGeometry) {
    drawGeometry(props.routesGeometry)
  }
})

onUnmounted(() => {
  if (map) {
    map.remove()
    map = null
  }
})
</script>

<template>
  <div ref="mapContainer" class="map-container"></div>
</template>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
  min-height: 500px;
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
  z-index: 1;
}
</style>
