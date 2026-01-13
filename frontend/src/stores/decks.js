import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { decksApi } from '@/api/decks'

export const useDecksStore = defineStore('decks', () => {
  // State
  const decks = ref([])
  const currentDeck = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const pagination = ref({
    total: 0,
    skip: 0,
    limit: 20
  })

  // Getters
  const deckCount = computed(() => decks.value.length)
  const totalCards = computed(() =>
    decks.value.reduce((sum, deck) => sum + (deck.cardCount || 0), 0)
  )
  const sortedDecks = computed(() =>
    [...decks.value].sort((a, b) =>
      new Date(b.updatedAt) - new Date(a.updatedAt)
    )
  )
  const getDeckById = computed(() => (id) =>
    decks.value.find(deck => deck.id === id)
  )

  // Actions
  async function fetchDecks(params = {}) {
    loading.value = true
    error.value = null
    try {
      const response = await decksApi.getAll({
        skip: pagination.value.skip,
        limit: pagination.value.limit,
        ...params
      })

      if (Array.isArray(response)) {
        decks.value = response
      } else {
        decks.value = response.items || response.decks || []
        pagination.value.total = response.total || decks.value.length
      }

      return decks.value
    } catch (err) {
      error.value = err.message || 'Failed to fetch decks'
      return []
    } finally {
      loading.value = false
    }
  }

  async function fetchDeck(id) {
    loading.value = true
    error.value = null
    try {
      currentDeck.value = await decksApi.getById(id)
      return currentDeck.value
    } catch (err) {
      error.value = err.message || 'Failed to fetch deck'
      return null
    } finally {
      loading.value = false
    }
  }

  async function createDeck(deckData) {
    loading.value = true
    error.value = null
    try {
      const newDeck = await decksApi.create(deckData)
      decks.value.unshift(newDeck)
      return newDeck
    } catch (err) {
      error.value = err.message || 'Failed to create deck'
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateDeck(id, deckData) {
    loading.value = true
    error.value = null
    try {
      const updatedDeck = await decksApi.update(id, deckData)
      const index = decks.value.findIndex(d => d.id === id)
      if (index !== -1) {
        decks.value[index] = updatedDeck
      }
      if (currentDeck.value?.id === id) {
        currentDeck.value = updatedDeck
      }
      return updatedDeck
    } catch (err) {
      error.value = err.message || 'Failed to update deck'
      return null
    } finally {
      loading.value = false
    }
  }

  async function deleteDeck(id) {
    loading.value = true
    error.value = null
    try {
      await decksApi.delete(id)
      decks.value = decks.value.filter(d => d.id !== id)
      if (currentDeck.value?.id === id) {
        currentDeck.value = null
      }
      return true
    } catch (err) {
      error.value = err.message || 'Failed to delete deck'
      return false
    } finally {
      loading.value = false
    }
  }

  async function fetchDeckStats(id) {
    try {
      return await decksApi.getStats(id)
    } catch (err) {
      error.value = err.message || 'Failed to fetch deck stats'
      return null
    }
  }

  async function exportDeck(id, format = 'apkg') {
    loading.value = true
    error.value = null
    try {
      const data = await decksApi.export(id, format)

      // Handle blob download
      if (data instanceof Blob) {
        const deck = decks.value.find(d => d.id === id)
        const filename = `${deck?.name || 'deck'}.${format}`
        const url = window.URL.createObjectURL(data)
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
      }

      return true
    } catch (err) {
      error.value = err.message || 'Failed to export deck'
      return false
    } finally {
      loading.value = false
    }
  }

  async function importCards(deckId, file, format = 'csv') {
    loading.value = true
    error.value = null
    try {
      const result = await decksApi.import(deckId, file, format)
      // Refresh deck to get updated card count
      await fetchDeck(deckId)
      return result
    } catch (err) {
      error.value = err.message || 'Failed to import cards'
      return null
    } finally {
      loading.value = false
    }
  }

  async function cloneDeck(id, newName) {
    loading.value = true
    error.value = null
    try {
      const clonedDeck = await decksApi.clone(id, newName)
      decks.value.unshift(clonedDeck)
      return clonedDeck
    } catch (err) {
      error.value = err.message || 'Failed to clone deck'
      return null
    } finally {
      loading.value = false
    }
  }

  function setCurrentDeck(deck) {
    currentDeck.value = deck
  }

  function clearCurrentDeck() {
    currentDeck.value = null
  }

  function clearError() {
    error.value = null
  }

  return {
    // State
    decks,
    currentDeck,
    loading,
    error,
    pagination,
    // Getters
    deckCount,
    totalCards,
    sortedDecks,
    getDeckById,
    // Actions
    fetchDecks,
    fetchDeck,
    createDeck,
    updateDeck,
    deleteDeck,
    fetchDeckStats,
    exportDeck,
    importCards,
    cloneDeck,
    setCurrentDeck,
    clearCurrentDeck,
    clearError
  }
})
