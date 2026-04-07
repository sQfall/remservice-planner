import { defineStore } from 'pinia'
import { fetchRequests, fetchRequest, createRequest, updateRequest, deleteRequest } from '@/api'

export const useRequestsStore = defineStore('requests', {
  state: () => ({
    items: [],
    loading: false,
    error: null,
    filters: {
      date: null,
      status: null,
      work_type: null,
      priority: null,
    },
  }),

  getters: {
    filteredItems: (state) => {
      let items = state.items
      const { date, status, work_type, priority } = state.filters

      if (date) {
        items = items.filter((r) => {
          if (!r.planned_at) return false
          return r.planned_at.startsWith(date)
        })
      }
      if (status) {
        items = items.filter((r) => r.status === status)
      }
      if (work_type) {
        items = items.filter((r) => r.work_type === work_type)
      }
      if (priority) {
        items = items.filter((r) => r.priority === priority)
      }

      return items
    },
  },

  actions: {
    async loadRequests() {
      this.loading = true
      this.error = null
      try {
        // Загружаем все заявки без фильтров, фильтрация делается на клиенте в filteredItems
        this.items = await fetchRequests({})
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async loadRequest(id) {
      this.loading = true
      this.error = null
      try {
        const request = await fetchRequest(id)
        const index = this.items.findIndex((r) => r.id === id)
        if (index !== -1) {
          this.items[index] = request
        } else {
          this.items.push(request)
        }
        return request
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async createRequest(data) {
      this.loading = true
      this.error = null
      try {
        const created = await createRequest(data)
        this.items.unshift(created)
        return created
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async updateRequest(id, data) {
      this.loading = true
      this.error = null
      try {
        const updated = await updateRequest(id, data)
        const index = this.items.findIndex((r) => r.id === id)
        if (index !== -1) {
          this.items[index] = updated
        }
        return updated
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async deleteRequest(id) {
      this.loading = true
      this.error = null
      try {
        await deleteRequest(id)
        this.items = this.items.filter((r) => r.id !== id)
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },
  },
})
