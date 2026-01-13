import apiClient from './client'

export const generationApi = {
  /**
   * Generate cards from text content
   * @param {Object} params - Generation parameters
   * @param {string} params.content - Text content to generate cards from
   * @param {string} params.deckId - Target deck ID
   * @param {number} params.numCards - Number of cards to generate
   * @param {string} params.difficulty - Difficulty level (easy, medium, hard)
   * @param {string} params.cardType - Card type (basic, cloze, reversed)
   * @param {string} params.language - Language for cards
   * @returns {Promise} Generated cards
   */
  async fromText(params) {
    const response = await apiClient.post('/generate/text', params)
    return response.data
  },

  /**
   * Generate cards from uploaded file
   * @param {File} file - Uploaded file (PDF, DOCX, TXT, MD)
   * @param {Object} options - Generation options
   * @param {string} options.deckId - Target deck ID
   * @param {number} options.numCards - Number of cards to generate
   * @param {string} options.difficulty - Difficulty level
   * @param {string} options.cardType - Card type
   * @returns {Promise} Generated cards
   */
  async fromFile(file, options) {
    const formData = new FormData()
    formData.append('file', file)
    Object.keys(options).forEach(key => {
      formData.append(key, options[key])
    })

    const response = await apiClient.post('/generate/file', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 120000 // 2 minutes for file processing
    })
    return response.data
  },

  /**
   * Generate cards from URL
   * @param {Object} params - Generation parameters
   * @param {string} params.url - URL to extract content from
   * @param {string} params.deckId - Target deck ID
   * @param {number} params.numCards - Number of cards to generate
   * @param {string} params.difficulty - Difficulty level
   * @param {string} params.cardType - Card type
   * @returns {Promise} Generated cards
   */
  async fromUrl(params) {
    const response = await apiClient.post('/generate/url', params, {
      timeout: 120000
    })
    return response.data
  },

  /**
   * Generate cards from topic
   * @param {Object} params - Generation parameters
   * @param {string} params.topic - Topic to generate cards about
   * @param {string} params.deckId - Target deck ID
   * @param {number} params.numCards - Number of cards to generate
   * @param {string} params.difficulty - Difficulty level
   * @param {string} params.depth - Coverage depth (overview, detailed, comprehensive)
   * @returns {Promise} Generated cards
   */
  async fromTopic(params) {
    const response = await apiClient.post('/generate/topic', params)
    return response.data
  },

  /**
   * Start async generation job
   * @param {Object} params - Generation parameters
   * @returns {Promise} Job ID and status
   */
  async startJob(params) {
    const response = await apiClient.post('/generate/job', params)
    return response.data
  },

  /**
   * Get generation job status
   * @param {string} jobId - Job ID
   * @returns {Promise} Job status and progress
   */
  async getJobStatus(jobId) {
    const response = await apiClient.get(`/generate/job/${jobId}`)
    return response.data
  },

  /**
   * Cancel generation job
   * @param {string} jobId - Job ID
   * @returns {Promise}
   */
  async cancelJob(jobId) {
    const response = await apiClient.delete(`/generate/job/${jobId}`)
    return response.data
  },

  /**
   * Get generation history
   * @param {Object} params - Query parameters
   * @param {number} params.skip - Number of items to skip
   * @param {number} params.limit - Number of items to return
   * @returns {Promise} List of past generations
   */
  async getHistory(params = {}) {
    const response = await apiClient.get('/generate/history', { params })
    return response.data
  },

  /**
   * Regenerate specific cards
   * @param {string[]} cardIds - Card IDs to regenerate
   * @param {Object} options - Regeneration options
   * @returns {Promise} Regenerated cards
   */
  async regenerate(cardIds, options = {}) {
    const response = await apiClient.post('/generate/regenerate', {
      cardIds,
      ...options
    })
    return response.data
  },

  /**
   * Get available generation models
   * @returns {Promise} List of available AI models
   */
  async getModels() {
    const response = await apiClient.get('/generate/models')
    return response.data
  },

  /**
   * Preview generation without saving
   * @param {Object} params - Same as generation params
   * @returns {Promise} Preview of cards that would be generated
   */
  async preview(params) {
    const response = await apiClient.post('/generate/preview', params)
    return response.data
  }
}

export default generationApi
