import { defineStore } from 'pinia'
import { fetchBrigades } from '@/api'

export const useBrigadesStore = defineStore('brigades', {
  state: () => ({
    items: [],
    loading: false,
    error: null,
  }),

  getters: {
    byId: (state) => (id) => {
      return state.items.find((b) => b.id === id) || null
    },
  },

  actions: {
    async loadBrigades() {
      this.loading = true
      this.error = null
      try {
        this.items = await fetchBrigades()
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },
  },
})
