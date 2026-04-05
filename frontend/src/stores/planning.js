import { defineStore } from 'pinia'
import {
  runAutoPlanning,
  fetchPlan,
  fetchPlanStatistics,
  fetchRoutesGeometry,
  savePlan,
  resetPlan,
} from '@/api'

export const usePlanningStore = defineStore('planning', {
  state: () => ({
    plan: null,
    brigades: [],
    statistics: [],
    routesGeometry: null,
    loading: false,
    error: null,
    selectedDate: null,
    selectedBrigadeId: null,
  }),

  actions: {
    async runPlanning(date, useOrTools = false) {
      this.loading = true
      this.error = null
      try {
        this.plan = await runAutoPlanning(date, useOrTools)
        this.selectedDate = date
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async loadPlan(date) {
      this.loading = true
      this.error = null
      try {
        this.plan = await fetchPlan(date)
        this.selectedDate = date
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async loadStatistics(date) {
      this.loading = true
      this.error = null
      try {
        this.statistics = await fetchPlanStatistics(date)
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async loadGeometry(date) {
      this.loading = true
      this.error = null
      try {
        this.routesGeometry = await fetchRoutesGeometry(date)
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async savePlan(date) {
      this.loading = true
      this.error = null
      try {
        await savePlan(date)
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async resetPlan(date) {
      this.loading = true
      this.error = null
      try {
        await resetPlan(date)
        this.plan = null
        this.statistics = []
        this.routesGeometry = null
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },
  },
})
