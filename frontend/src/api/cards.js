import apiClient from './client'

export const cardsApi = {
  /**
   * Get all cards (optionally filtered by deck)
   * @param {Object} params - Query parameters
   * @param {string} params.deckId - Filter by deck ID
   * @param {number} params.skip - Number of items to skip
   * @param {number} params.limit - Number of items to return
   * @param {string} params.search - Search query
   * @param {string} params.status - Filter by status (new, learning, review, suspended)
   * @returns {Promise} List of cards
   */
  async getAll(params = {}) {
    const response = await apiClient.get('/cards', { params })
    return response.data
  },

  /**
   * Get a single card by ID
   * @param {string} id - Card ID
   * @returns {Promise} Card data
   */
  async getById(id) {
    const response = await apiClient.get(`/cards/${id}`)
    return response.data
  },

  /**
   * Create a new card
   * @param {Object} cardData - Card data
   * @param {string} cardData.deckId - Deck ID
   * @param {string} cardData.front - Card front content
   * @param {string} cardData.back - Card back content
   * @param {string[]} cardData.tags - Card tags
   * @param {Object} cardData.metadata - Additional metadata
   * @returns {Promise} Created card data
   */
  async create(cardData) {
    const response = await apiClient.post('/cards', cardData)
    return response.data
  },

  /**
   * Create multiple cards at once
   * @param {Object[]} cardsData - Array of card data
   * @returns {Promise} Created cards data
   */
  async createBulk(cardsData) {
    const response = await apiClient.post('/cards/bulk', { cards: cardsData })
    return response.data
  },

  /**
   * Update a card
   * @param {string} id - Card ID
   * @param {Object} cardData - Updated card data
   * @returns {Promise} Updated card data
   */
  async update(id, cardData) {
    const response = await apiClient.put(`/cards/${id}`, cardData)
    return response.data
  },

  /**
   * Delete a card
   * @param {string} id - Card ID
   * @returns {Promise}
   */
  async delete(id) {
    const response = await apiClient.delete(`/cards/${id}`)
    return response.data
  },

  /**
   * Delete multiple cards
   * @param {string[]} ids - Card IDs to delete
   * @returns {Promise}
   */
  async deleteBulk(ids) {
    const response = await apiClient.post('/cards/bulk-delete', { ids })
    return response.data
  },

  /**
   * Submit review for a card
   * @param {string} id - Card ID
   * @param {Object} review - Review data
   * @param {number} review.rating - Rating (1-4: again, hard, good, easy)
   * @param {number} review.timeSpent - Time spent on review in ms
   * @returns {Promise} Updated card with new schedule
   */
  async submitReview(id, review) {
    const response = await apiClient.post(`/cards/${id}/review`, review)
    return response.data
  },

  /**
   * Suspend a card
   * @param {string} id - Card ID
   * @returns {Promise} Updated card
   */
  async suspend(id) {
    const response = await apiClient.post(`/cards/${id}/suspend`)
    return response.data
  },

  /**
   * Unsuspend a card
   * @param {string} id - Card ID
   * @returns {Promise} Updated card
   */
  async unsuspend(id) {
    const response = await apiClient.post(`/cards/${id}/unsuspend`)
    return response.data
  },

  /**
   * Move card to another deck
   * @param {string} id - Card ID
   * @param {string} deckId - Target deck ID
   * @returns {Promise} Updated card
   */
  async move(id, deckId) {
    const response = await apiClient.post(`/cards/${id}/move`, { deckId })
    return response.data
  },

  /**
   * Move multiple cards to another deck
   * @param {string[]} ids - Card IDs
   * @param {string} deckId - Target deck ID
   * @returns {Promise}
   */
  async moveBulk(ids, deckId) {
    const response = await apiClient.post('/cards/bulk-move', { ids, deckId })
    return response.data
  },

  /**
   * Get card learning history
   * @param {string} id - Card ID
   * @returns {Promise} Review history
   */
  async getHistory(id) {
    const response = await apiClient.get(`/cards/${id}/history`)
    return response.data
  },

  /**
   * Reset card learning progress
   * @param {string} id - Card ID
   * @returns {Promise} Reset card
   */
  async reset(id) {
    const response = await apiClient.post(`/cards/${id}/reset`)
    return response.data
  }
}

export default cardsApi
