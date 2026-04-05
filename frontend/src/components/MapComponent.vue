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

  // Рисуем сегменты
  geometry.features.forEach((feature) => {
    const props = feature.properties || {}
    const isGarage = props.is_garage_segment
    const bid = props.brigade_id
    const brigadeIdx = brigadeIndices[bid] ?? 0
    const color = getBrigadeColor(brigadeIdx)

    if (feature.geometry.type !== 'LineString') return

    const latlngs = feature.geometry.coordinates.map(([lon, lat]) => [lat, lon])

    if (isGarage) {
      // Серый пунктир для гаражных сегментов
      const line = L.polyline(latlngs, {
        color: '#94a3b8',
        weight: 2,
        dashArray: '6, 6',
        opacity: 0.7,
      })
      line.addTo(layersGroup)
    } else {
      const line = L.polyline(latlngs, {
        color,
        weight: 3,
        opacity: 0.85,
      })
      line.addTo(layersGroup)

      // Popup с именем бригады
      if (props.brigade_name) {
        line.bindPopup(props.brigade_name)
      }
    }
  })

  // Собираем точки маршрутов и гаражи из сегментов
  const pointSet = new Map() // key: "lat,lon" -> { lat, lon, brigadeId, brigadeName, sequences: [], isGarage: bool }

  geometry.features.forEach((feature) => {
    if (feature.geometry.type !== 'LineString') return

    const props = feature.properties || {}
    const coords = feature.geometry.coordinates
    const isGarage = props.is_garage_segment
    const brigadeName = props.brigade_name
    const bid = props.brigade_id

    // Берём только первую и последнюю точку каждого сегмента как маркеры
    const endpoints = [coords[0], coords[coords.length - 1]]

    endpoints.forEach(([lon, lat]) => {
      const key = `${lat.toFixed(6)},${lon.toFixed(6)}`
      if (!pointSet.has(key)) {
        pointSet.set(key, {
          lat,
          lon,
          brigadeId: bid,
          brigadeName,
          sequences: [],
          isGarage: isGarage,
        })
      }
    })
  })

  // Добавляем маркеры точек
  pointSet.forEach((point, _key) => {
    const brigadeIdx = brigadeIndices[point.brigadeId] ?? 0
    const color = getBrigadeColor(brigadeIdx)

    if (point.isGarage) {
      // Маркер гаража — больший радиус
      const marker = L.circleMarker([point.lat, point.lon], {
        radius: 10,
        fillColor: color,
        color: '#fff',
        weight: 2,
        fillOpacity: 0.9,
      })
      marker.bindPopup(`Гараж: ${point.brigadeName || point.brigadeId}`)
      marker.addTo(layersGroup)
    } else {
      // Маркер точки маршрута
      const marker = L.circleMarker([point.lat, point.lon], {
        radius: 8,
        fillColor: color,
        color: '#fff',
        weight: 2,
        fillOpacity: 0.85,
      })

      const popupContent = point.brigadeName
        ? `<div>${point.brigadeName}</div>`
        : `Бригада #${point.brigadeId}`
      marker.bindPopup(popupContent)
      marker.addTo(layersGroup)
    }
  })

  // Fit bounds
  if (pointSet.size > 0) {
    const bounds = [...pointSet.values()].map((p) => [p.lat, p.lon])
    map.fitBounds(bounds, { padding: [30, 30] })
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
