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

  const pointSet = new Map() // Для fitBounds
  const brigadePoints = {} // { brigadeId: [{lon, lat, label}] }

  // Вспомогательная функция для получения цвета по ID бригады
  function getBrigadeColor(bid) {
    return BRIGADE_COLORS[bid % BRIGADE_COLORS.length]
  }

  // 1. Сначала собираем точки (заявки и гаражи), чтобы потом определять подписи для линий
  geometry.features.forEach((feature) => {
    if (feature.geometry.type !== 'Point') return
    const props = feature.properties || {}
    const bid = props.brigade_id
    const [lon, lat] = feature.geometry.coordinates

    if (!brigadePoints[bid]) brigadePoints[bid] = []

    let label = ''
    if (props.type === 'garage') {
      label = `Гараж (${props.brigade_name || 'Бригада #' + bid})`
    } else if (props.type === 'request') {
      label = props.address || `Заявка #${props.request_id}`
    } else {
      label = `Точка`
    }

    brigadePoints[bid].push({ lon, lat, label })
  })

  // Вспомогательная функция для поиска ближайшей точки к координатам линии
  function getNearestLabel(lon, lat, points) {
    if (!points || points.length === 0) return '?'
    let minDist = Infinity
    let label = '?'
    for (const p of points) {
      const dist = (p.lon - lon) ** 2 + (p.lat - lat) ** 2
      if (dist < minDist) {
        minDist = dist
        label = p.label
      }
    }
    return label
  }

  // 2. Рисуем линии
  geometry.features.forEach((feature) => {
    const props = feature.properties || {}
    const bid = props.brigade_id
    // Всегда используем цвет по ID бригады — игнорируем props.color от сервера
    const color = getBrigadeColor(bid)

    // Обработка точек (Point)
    if (feature.geometry.type === 'Point') {
      const [lon, lat] = feature.geometry.coordinates
      const pointType = props.type // 'request' или 'garage'
      const color = getBrigadeColor(bid)
      
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
      const props = feature.properties || {}
      // Проверяем тип сегмента безопасно
      const rawType = props.garage_segment_type
      const garageType = (rawType && typeof rawType === 'object') ? rawType.value : rawType
      const isReturnToGarage = garageType === 'last_to_garage'
      
      const latlngs = feature.geometry.coordinates.map(([lon, lat]) => [lat, lon])

      // Определяем начальную и конечную точки сегмента для попапа
      const coords = feature.geometry.coordinates // [lon, lat]
      const start = coords[0]
      const end = coords[coords.length - 1]
      const points = brigadePoints[bid] || []
      
      const startLabel = getNearestLabel(start[0], start[1], points)
      const endLabel = getNearestLabel(end[0], end[1], points)
      
      const popupContent = `<b>${props.brigade_name || 'Бригада #' + bid}</b><br>${startLabel} → ${endLabel}`

      let line
      if (isReturnToGarage) {
        // Пунктир (возврат в гараж)
        line = L.polyline(latlngs, {
          color: color,
          weight: 5,
          dashArray: '5, 8',
          opacity: 0.8,
        })
      } else {
        // Сплошная линия (между заявками и от гаража)
        line = L.polyline(latlngs, {
          color: color,
          weight: 6,
          opacity: 0.9,
        })
      }
      
      // Привязываем попап к обоим типам линий
      line.bindPopup(popupContent)
      line.addTo(layersGroup)

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
    const belongs = content.includes(brigadeId) || layer.options?.color === getBrigadeColor(brigadeId)

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
