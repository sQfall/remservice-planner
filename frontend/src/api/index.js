import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API error:', error.response?.data ?? error.message)
    return Promise.reject(error)
  }
)

// ─── Заявки ───────────────────────────────────────────────

export async function fetchRequests(params = {}) {
  const { data } = await api.get('/requests', { params })
  return data
}

export async function fetchRequest(id) {
  const { data } = await api.get(`/requests/${id}`)
  return data
}

export async function createRequest(data) {
  const { data: result } = await api.post('/requests', data)
  return result
}

export async function updateRequest(id, data) {
  const { data: result } = await api.put(`/requests/${id}`, data)
  return result
}

export async function deleteRequest(id) {
  await api.delete(`/requests/${id}`)
}

// ─── Бригады ──────────────────────────────────────────────

export async function fetchBrigades() {
  const { data } = await api.get('/brigades')
  return data
}

// ─── Планирование ─────────────────────────────────────────

export async function runAutoPlanning(date, useOrTools = false) {
  const { data } = await api.post('/planning/auto', null, {
    params: { plan_date: date, use_or_tools: useOrTools },
  })
  return data
}

export async function fetchPlan(date) {
  const { data } = await api.get(`/planning/${date}`)
  return data
}

export async function fetchPlanBrigades(date) {
  const { data } = await api.get(`/planning/${date}/brigades`)
  return data
}

export async function fetchPlanStatistics(date) {
  const { data } = await api.get(`/planning/${date}/statistics`)
  return data
}

export async function fetchRoutesGeometry(date) {
  const { data } = await api.get(`/planning/${date}/routes-geometry`)
  return data
}

export async function savePlan(date) {
  const { data } = await api.post('/planning/save', { plan_date: date })
  return data
}

export async function resetPlan(date) {
  await api.post('/planning/reset', { plan_date: date })
}

// ─── Маршрутные листы ─────────────────────────────────────

export async function fetchRouteSheets(date) {
  const { data } = await api.get(`/route-sheets/${date}`)
  return data
}

export async function downloadRoutePdf(date, brigadeId) {
  const { data } = await api.get(`/route-sheets/${date}/${brigadeId}/pdf`, {
    responseType: 'blob',
  })
  return data
}

export async function issueRouteSheets(date) {
  const { data } = await api.post(`/route-sheets/${date}/issue`)
  return data
}
