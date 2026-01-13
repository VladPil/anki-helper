import apiClient from './client'

export const chatApi = {
  /**
   * Send a chat message and get AI response
   * @param {Object} params - Chat parameters
   * @param {string} params.message - User message
   * @param {string} params.conversationId - Conversation ID (optional)
   * @param {string} params.deckId - Context deck ID (optional)
   * @param {Object} params.context - Additional context
   * @returns {Promise} AI response
   */
  async sendMessage(params) {
    const response = await apiClient.post('/chat/message', params)
    return response.data
  },

  /**
   * Send a chat message with streaming response
   * @param {Object} params - Chat parameters
   * @param {Function} onChunk - Callback for each chunk
   * @param {Function} onComplete - Callback when complete
   * @param {Function} onError - Callback on error
   * @returns {Promise}
   */
  async sendMessageStream(params, onChunk, onComplete, onError) {
    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(params)
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          onComplete?.()
          break
        }

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n').filter(line => line.trim())

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') {
              onComplete?.()
              return
            }
            try {
              const parsed = JSON.parse(data)
              onChunk?.(parsed)
            } catch {
              onChunk?.({ content: data })
            }
          }
        }
      }
    } catch (error) {
      onError?.(error)
      throw error
    }
  },

  /**
   * Get conversation history
   * @param {string} conversationId - Conversation ID
   * @returns {Promise} Conversation messages
   */
  async getConversation(conversationId) {
    const response = await apiClient.get(`/chat/conversation/${conversationId}`)
    return response.data
  },

  /**
   * Get all conversations
   * @param {Object} params - Query parameters
   * @param {number} params.skip - Number to skip
   * @param {number} params.limit - Number to return
   * @returns {Promise} List of conversations
   */
  async getConversations(params = {}) {
    const response = await apiClient.get('/chat/conversations', { params })
    return response.data
  },

  /**
   * Create a new conversation
   * @param {Object} data - Conversation data
   * @param {string} data.title - Conversation title
   * @param {string} data.deckId - Associated deck (optional)
   * @returns {Promise} Created conversation
   */
  async createConversation(data = {}) {
    const response = await apiClient.post('/chat/conversation', data)
    return response.data
  },

  /**
   * Delete a conversation
   * @param {string} conversationId - Conversation ID
   * @returns {Promise}
   */
  async deleteConversation(conversationId) {
    const response = await apiClient.delete(`/chat/conversation/${conversationId}`)
    return response.data
  },

  /**
   * Clear conversation history
   * @param {string} conversationId - Conversation ID
   * @returns {Promise}
   */
  async clearConversation(conversationId) {
    const response = await apiClient.post(`/chat/conversation/${conversationId}/clear`)
    return response.data
  },

  /**
   * Generate cards from chat conversation
   * @param {string} conversationId - Conversation ID
   * @param {Object} options - Generation options
   * @param {string} options.deckId - Target deck
   * @param {number} options.numCards - Number of cards
   * @returns {Promise} Generated cards
   */
  async generateCardsFromChat(conversationId, options) {
    const response = await apiClient.post(
      `/chat/conversation/${conversationId}/generate-cards`,
      options
    )
    return response.data
  },

  /**
   * Ask a question about specific cards
   * @param {Object} params - Question parameters
   * @param {string} params.question - The question
   * @param {string[]} params.cardIds - Related card IDs
   * @returns {Promise} AI response
   */
  async askAboutCards(params) {
    const response = await apiClient.post('/chat/ask-cards', params)
    return response.data
  },

  /**
   * Get study recommendations based on chat
   * @param {string} conversationId - Conversation ID
   * @returns {Promise} Study recommendations
   */
  async getRecommendations(conversationId) {
    const response = await apiClient.get(
      `/chat/conversation/${conversationId}/recommendations`
    )
    return response.data
  },

  /**
   * Update conversation title
   * @param {string} conversationId - Conversation ID
   * @param {string} title - New title
   * @returns {Promise} Updated conversation
   */
  async updateConversationTitle(conversationId, title) {
    const response = await apiClient.patch(
      `/chat/conversation/${conversationId}`,
      { title }
    )
    return response.data
  }
}

export default chatApi
