import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { cardsApi } from '@/api/cards'

export const useCardsStore = defineStore('cards', () => {
  // State
  const cards = ref([])
  const currentCard = ref(null)
  const selectedCards = ref([])
  const loading = ref(false)
  const error = ref(null)
  const pagination = ref({
    total: 0,
    skip: 0,
    limit: 50
  })
  const filters = ref({
    deckId: null,
    search: '',
    status: null
  })

  // Getters
  const cardCount = computed(() => cards.value.length)
  const hasSelectedCards = computed(() => selectedCards.value.length > 0)
  const selectedCount = computed(() => selectedCards.value.length)
  const filteredCards = computed(() => {
    let result = [...cards.value]

    if (filters.value.search) {
      const search = filters.value.search.toLowerCase()
      result = result.filter(card =>
        card.front.toLowerCase().includes(search) ||
        card.back.toLowerCase().includes(search)
      )
    }

    if (filters.value.status) {
      result = result.filter(card => card.status === filters.value.status)
    }

    return result
  })

  // Actions
  async function fetchCards(params = {}) {
    loading.value = true
    error.value = null
    try {
      const response = await cardsApi.getAll({
        skip: pagination.value.skip,
        limit: pagination.value.limit,
        ...filters.value,
        ...params
      })

      if (Array.isArray(response)) {
        cards.value = response
      } else {
        cards.value = response.items || response.cards || []
        pagination.value.total = response.total || cards.value.length
      }

      return cards.value
    } catch (err) {
      error.value = err.message || 'Failed to fetch cards'
      return []
    } finally {
      loading.value = false
    }
  }

  async function fetchCard(id) {
    loading.value = true
    error.value = null
    try {
      currentCard.value = await cardsApi.getById(id)
      return currentCard.value
    } catch (err) {
      error.value = err.message || 'Failed to fetch card'
      return null
    } finally {
      loading.value = false
    }
  }

  async function createCard(cardData) {
    loading.value = true
    error.value = null
    try {
      const newCard = await cardsApi.create(cardData)
      cards.value.unshift(newCard)
      return newCard
    } catch (err) {
      error.value = err.message || 'Failed to create card'
      return null
    } finally {
      loading.value = false
    }
  }

  async function createCards(cardsData) {
    loading.value = true
    error.value = null
    try {
      const result = await cardsApi.createBulk(cardsData)
      const newCards = result.cards || result
      cards.value = [...newCards, ...cards.value]
      return newCards
    } catch (err) {
      error.value = err.message || 'Failed to create cards'
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateCard(id, cardData) {
    loading.value = true
    error.value = null
    try {
      const updatedCard = await cardsApi.update(id, cardData)
      const index = cards.value.findIndex(c => c.id === id)
      if (index !== -1) {
        cards.value[index] = updatedCard
      }
      if (currentCard.value?.id === id) {
        currentCard.value = updatedCard
      }
      return updatedCard
    } catch (err) {
      error.value = err.message || 'Failed to update card'
      return null
    } finally {
      loading.value = false
    }
  }

  async function deleteCard(id) {
    loading.value = true
    error.value = null
    try {
      await cardsApi.delete(id)
      cards.value = cards.value.filter(c => c.id !== id)
      selectedCards.value = selectedCards.value.filter(cid => cid !== id)
      if (currentCard.value?.id === id) {
        currentCard.value = null
      }
      return true
    } catch (err) {
      error.value = err.message || 'Failed to delete card'
      return false
    } finally {
      loading.value = false
    }
  }

  async function deleteCards(ids) {
    loading.value = true
    error.value = null
    try {
      await cardsApi.deleteBulk(ids)
      cards.value = cards.value.filter(c => !ids.includes(c.id))
      selectedCards.value = selectedCards.value.filter(id => !ids.includes(id))
      return true
    } catch (err) {
      error.value = err.message || 'Failed to delete cards'
      return false
    } finally {
      loading.value = false
    }
  }

  async function submitReview(id, review) {
    loading.value = true
    error.value = null
    try {
      const updatedCard = await cardsApi.submitReview(id, review)
      const index = cards.value.findIndex(c => c.id === id)
      if (index !== -1) {
        cards.value[index] = updatedCard
      }
      return updatedCard
    } catch (err) {
      error.value = err.message || 'Failed to submit review'
      return null
    } finally {
      loading.value = false
    }
  }

  async function suspendCard(id) {
    try {
      const updatedCard = await cardsApi.suspend(id)
      const index = cards.value.findIndex(c => c.id === id)
      if (index !== -1) {
        cards.value[index] = updatedCard
      }
      return updatedCard
    } catch (err) {
      error.value = err.message || 'Failed to suspend card'
      return null
    }
  }

  async function unsuspendCard(id) {
    try {
      const updatedCard = await cardsApi.unsuspend(id)
      const index = cards.value.findIndex(c => c.id === id)
      if (index !== -1) {
        cards.value[index] = updatedCard
      }
      return updatedCard
    } catch (err) {
      error.value = err.message || 'Failed to unsuspend card'
      return null
    }
  }

  async function moveCards(ids, deckId) {
    loading.value = true
    error.value = null
    try {
      await cardsApi.moveBulk(ids, deckId)
      // Remove moved cards if we're viewing a specific deck
      if (filters.value.deckId && filters.value.deckId !== deckId) {
        cards.value = cards.value.filter(c => !ids.includes(c.id))
      }
      selectedCards.value = []
      return true
    } catch (err) {
      error.value = err.message || 'Failed to move cards'
      return false
    } finally {
      loading.value = false
    }
  }

  async function getCardHistory(id) {
    try {
      return await cardsApi.getHistory(id)
    } catch (err) {
      error.value = err.message || 'Failed to get card history'
      return null
    }
  }

  async function resetCard(id) {
    try {
      const updatedCard = await cardsApi.reset(id)
      const index = cards.value.findIndex(c => c.id === id)
      if (index !== -1) {
        cards.value[index] = updatedCard
      }
      return updatedCard
    } catch (err) {
      error.value = err.message || 'Failed to reset card'
      return null
    }
  }

  async function approveCard(id, reason = null) {
    loading.value = true
    error.value = null
    try {
      const updatedCard = await cardsApi.approve(id, reason)
      const index = cards.value.findIndex(c => c.id === id)
      if (index !== -1) {
        cards.value[index] = updatedCard
      }
      return updatedCard
    } catch (err) {
      error.value = err.message || 'Failed to approve card'
      return null
    } finally {
      loading.value = false
    }
  }

  async function rejectCard(id, reason) {
    loading.value = true
    error.value = null
    try {
      const updatedCard = await cardsApi.reject(id, reason)
      const index = cards.value.findIndex(c => c.id === id)
      if (index !== -1) {
        cards.value[index] = updatedCard
      }
      return updatedCard
    } catch (err) {
      error.value = err.message || 'Failed to reject card'
      return null
    } finally {
      loading.value = false
    }
  }

  async function approveCards(ids) {
    loading.value = true
    error.value = null
    try {
      const result = await cardsApi.approveBulk(ids)
      // Update cards in the store
      if (result.created) {
        result.created.forEach(approvedCard => {
          const index = cards.value.findIndex(c => c.id === approvedCard.id)
          if (index !== -1) {
            cards.value[index] = approvedCard
          }
        })
      }
      selectedCards.value = []
      return result
    } catch (err) {
      error.value = err.message || 'Failed to approve cards'
      return null
    } finally {
      loading.value = false
    }
  }

  async function rejectCards(ids, reason) {
    loading.value = true
    error.value = null
    try {
      const result = await cardsApi.rejectBulk(ids, reason)
      // Update cards in the store
      if (result.created) {
        result.created.forEach(rejectedCard => {
          const index = cards.value.findIndex(c => c.id === rejectedCard.id)
          if (index !== -1) {
            cards.value[index] = rejectedCard
          }
        })
      }
      selectedCards.value = []
      return result
    } catch (err) {
      error.value = err.message || 'Failed to reject cards'
      return null
    } finally {
      loading.value = false
    }
  }

  // Selection management
  function selectCard(id) {
    if (!selectedCards.value.includes(id)) {
      selectedCards.value.push(id)
    }
  }

  function deselectCard(id) {
    selectedCards.value = selectedCards.value.filter(cid => cid !== id)
  }

  function toggleCardSelection(id) {
    if (selectedCards.value.includes(id)) {
      deselectCard(id)
    } else {
      selectCard(id)
    }
  }

  function selectAllCards() {
    selectedCards.value = cards.value.map(c => c.id)
  }

  function clearSelection() {
    selectedCards.value = []
  }

  // Filter management
  function setFilter(key, value) {
    filters.value[key] = value
  }

  function clearFilters() {
    filters.value = {
      deckId: null,
      search: '',
      status: null
    }
  }

  function setCurrentCard(card) {
    currentCard.value = card
  }

  function clearError() {
    error.value = null
  }

  return {
    // State
    cards,
    currentCard,
    selectedCards,
    loading,
    error,
    pagination,
    filters,
    // Getters
    cardCount,
    hasSelectedCards,
    selectedCount,
    filteredCards,
    // Actions
    fetchCards,
    fetchCard,
    createCard,
    createCards,
    updateCard,
    deleteCard,
    deleteCards,
    submitReview,
    suspendCard,
    unsuspendCard,
    moveCards,
    getCardHistory,
    resetCard,
    approveCard,
    rejectCard,
    approveCards,
    rejectCards,
    selectCard,
    deselectCard,
    toggleCardSelection,
    selectAllCards,
    clearSelection,
    setFilter,
    clearFilters,
    setCurrentCard,
    clearError
  }
})
