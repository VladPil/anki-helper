import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || null)
  const refreshToken = ref(localStorage.getItem('refreshToken') || null)
  const loading = ref(false)
  const error = ref(null)
  const isRefreshing = ref(false)

  // Getters
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const userEmail = computed(() => user.value?.email || '')
  const userName = computed(() => user.value?.username || user.value?.email?.split('@')[0] || '')

  // Actions
  async function login(credentials) {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.login(credentials)
      token.value = response.accessToken
      refreshToken.value = response.refreshToken
      localStorage.setItem('token', response.accessToken)
      if (response.refreshToken) {
        localStorage.setItem('refreshToken', response.refreshToken)
      }
      await fetchProfile()
      // Verify user was actually fetched
      if (!user.value) {
        error.value = 'Failed to fetch user profile'
        return false
      }
      return true
    } catch (err) {
      error.value = err.message || 'Login failed'
      return false
    } finally {
      loading.value = false
    }
  }

  async function register(userData) {
    loading.value = true
    error.value = null
    try {
      await authApi.register(userData)
      // Auto-login after registration
      return await login({
        email: userData.email,
        password: userData.password
      })
    } catch (err) {
      error.value = err.message || 'Registration failed'
      return false
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    const currentRefreshToken = refreshToken.value
    try {
      if (currentRefreshToken) {
        await authApi.logout(currentRefreshToken)
      }
    } catch {
      // Ignore logout errors
    } finally {
      user.value = null
      token.value = null
      refreshToken.value = null
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
    }
  }

  async function refreshAccessToken() {
    if (!refreshToken.value || isRefreshing.value) {
      return false
    }

    isRefreshing.value = true
    try {
      const response = await authApi.refreshToken(refreshToken.value)
      token.value = response.accessToken
      localStorage.setItem('token', response.accessToken)
      if (response.refreshToken) {
        refreshToken.value = response.refreshToken
        localStorage.setItem('refreshToken', response.refreshToken)
      }
      return true
    } catch (err) {
      // Refresh failed, logout user
      await logout()
      return false
    } finally {
      isRefreshing.value = false
    }
  }

  async function fetchProfile() {
    if (!token.value) return null

    loading.value = true
    try {
      user.value = await authApi.getProfile()
      return user.value
    } catch (err) {
      // If profile fetch fails, clear auth state
      if (err.response?.status === 401) {
        logout()
      }
      error.value = err.message
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateProfile(profileData) {
    loading.value = true
    error.value = null
    try {
      user.value = await authApi.updateProfile(profileData)
      return true
    } catch (err) {
      error.value = err.message || 'Failed to update profile'
      return false
    } finally {
      loading.value = false
    }
  }

  async function changePassword(passwords) {
    loading.value = true
    error.value = null
    try {
      await authApi.changePassword(passwords)
      return true
    } catch (err) {
      error.value = err.message || 'Failed to change password'
      return false
    } finally {
      loading.value = false
    }
  }

  async function requestPasswordReset(email) {
    loading.value = true
    error.value = null
    try {
      await authApi.requestPasswordReset(email)
      return true
    } catch (err) {
      error.value = err.message || 'Failed to request password reset'
      return false
    } finally {
      loading.value = false
    }
  }

  async function resetPassword(data) {
    loading.value = true
    error.value = null
    try {
      await authApi.resetPassword(data)
      return true
    } catch (err) {
      error.value = err.message || 'Failed to reset password'
      return false
    } finally {
      loading.value = false
    }
  }

  function clearError() {
    error.value = null
  }

  // Initialize - check if we have a token and fetch profile
  async function initialize() {
    if (token.value) {
      await fetchProfile()
    }
  }

  return {
    // State
    user,
    token,
    refreshToken,
    loading,
    error,
    isRefreshing,
    // Getters
    isAuthenticated,
    userEmail,
    userName,
    // Actions
    login,
    register,
    logout,
    refreshAccessToken,
    fetchProfile,
    updateProfile,
    changePassword,
    requestPasswordReset,
    resetPassword,
    clearError,
    initialize
  }
})
