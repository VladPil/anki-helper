import apiClient from './client'

export const decksApi = {
  /**
   * Get all decks for current user
   * @param {Object} params - Query parameters
   * @param {number} params.skip - Number of items to skip
   * @param {number} params.limit - Number of items to return
   * @param {string} params.search - Search query
   * @returns {Promise} List of decks
   */
  async getAll(params = {}) {
    const response = await apiClient.get('/decks', { params })
    return response.data
  },

  /**
   * Get a single deck by ID
   * @param {string} id - Deck ID
   * @returns {Promise} Deck data
   */
  async getById(id) {
    const response = await apiClient.get(`/decks/${id}`)
    return response.data
  },

  /**
   * Create a new deck
   * @param {Object} deckData - Deck data
   * @param {string} deckData.name - Deck name
   * @param {string} deckData.description - Deck description
   * @param {string[]} deckData.tags - Deck tags
   * @returns {Promise} Created deck data
   */
  async create(deckData) {
    const response = await apiClient.post('/decks', deckData)
    return response.data
  },

  /**
   * Update a deck
   * @param {string} id - Deck ID
   * @param {Object} deckData - Updated deck data
   * @returns {Promise} Updated deck data
   */
  async update(id, deckData) {
    const response = await apiClient.put(`/decks/${id}`, deckData)
    return response.data
  },

  /**
   * Delete a deck
   * @param {string} id - Deck ID
   * @returns {Promise}
   */
  async delete(id) {
    const response = await apiClient.delete(`/decks/${id}`)
    return response.data
  },

  /**
   * Get deck statistics
   * @param {string} id - Deck ID
   * @returns {Promise} Deck statistics
   */
  async getStats(id) {
    const response = await apiClient.get(`/decks/${id}/stats`)
    return response.data
  },

  /**
   * Export deck to Anki format
   * @param {string} id - Deck ID
   * @param {string} format - Export format (apkg, csv, json)
   * @returns {Promise} Export data or download URL
   */
  async export(id, format = 'apkg') {
    const response = await apiClient.get(`/decks/${id}/export`, {
      params: { format },
      responseType: format === 'apkg' ? 'blob' : 'json'
    })
    return response.data
  },

  /**
   * Import cards into a deck
   * @param {string} id - Deck ID
   * @param {File} file - Import file
   * @param {string} format - Import format
   * @returns {Promise} Import result
   */
  async import(id, file, format = 'csv') {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('format', format)

    const response = await apiClient.post(`/decks/${id}/import`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return response.data
  },

  /**
   * Get cards due for review in a deck
   * @param {string} id - Deck ID
   * @param {number} limit - Number of cards to return
   * @returns {Promise} List of due cards
   */
  async getDueCards(id, limit = 20) {
    const response = await apiClient.get(`/decks/${id}/due`, {
      params: { limit }
    })
    return response.data
  },

  /**
   * Clone a deck
   * @param {string} id - Deck ID
   * @param {string} newName - Name for the cloned deck
   * @returns {Promise} Cloned deck data
   */
  async clone(id, newName) {
    const response = await apiClient.post(`/decks/${id}/clone`, { name: newName })
    return response.data
  }
}

export default decksApi
