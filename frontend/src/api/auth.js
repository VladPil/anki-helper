import apiClient from './client'

export const authApi = {
  /**
   * Register a new user
   * @param {Object} userData - User registration data
   * @param {string} userData.email - User email
   * @param {string} userData.password - User password
   * @param {string} userData.username - Display name
   * @returns {Promise} Response with user data
   */
  async register(userData) {
    const payload = {
      email: userData.email,
      password: userData.password,
      display_name: userData.username || userData.display_name || userData.email.split('@')[0]
    }
    const response = await apiClient.post('/auth/register', payload)
    return response.data
  },

  /**
   * Login user
   * @param {Object} credentials - Login credentials
   * @param {string} credentials.email - User email
   * @param {string} credentials.password - User password
   * @returns {Promise} Response with token and user data
   */
  async login(credentials) {
    const response = await apiClient.post('/auth/login', {
      email: credentials.email,
      password: credentials.password
    })
    return response.data
  },

  /**
   * Logout current user
   * @param {string} refreshToken - Refresh token to invalidate
   * @returns {Promise}
   */
  async logout(refreshToken) {
    const response = await apiClient.post('/auth/logout', {
      refresh_token: refreshToken
    })
    return response.data
  },

  /**
   * Get current user profile
   * @returns {Promise} User profile data
   */
  async getProfile() {
    const response = await apiClient.get('/users/me')
    return response.data
  },

  /**
   * Update user profile
   * @param {Object} profileData - Profile update data
   * @returns {Promise} Updated user data
   */
  async updateProfile(profileData) {
    const response = await apiClient.put('/auth/me', profileData)
    return response.data
  },

  /**
   * Change password
   * @param {Object} passwords - Password data
   * @param {string} passwords.currentPassword - Current password
   * @param {string} passwords.newPassword - New password
   * @returns {Promise}
   */
  async changePassword(passwords) {
    const response = await apiClient.post('/auth/change-password', passwords)
    return response.data
  },

  /**
   * Request password reset
   * @param {string} email - User email
   * @returns {Promise}
   */
  async requestPasswordReset(email) {
    const response = await apiClient.post('/auth/forgot-password', { email })
    return response.data
  },

  /**
   * Reset password with token
   * @param {Object} data - Reset data
   * @param {string} data.token - Reset token
   * @param {string} data.newPassword - New password
   * @returns {Promise}
   */
  async resetPassword(data) {
    const response = await apiClient.post('/auth/reset-password', data)
    return response.data
  },

  /**
   * Refresh access token
   * @param {string} refreshToken - Refresh token
   * @returns {Promise} New access token pair
   */
  async refreshToken(refreshToken) {
    const response = await apiClient.post('/auth/refresh', {
      refresh_token: refreshToken
    })
    return response.data
  }
}

export default authApi
