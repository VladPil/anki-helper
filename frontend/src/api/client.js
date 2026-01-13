import axios from 'axios'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

// Utility functions for snake_case <-> camelCase conversion
function snakeToCamel(str) {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

function camelToSnake(str) {
  return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
}

function convertKeysToCamel(obj) {
  if (Array.isArray(obj)) {
    return obj.map(item => convertKeysToCamel(item))
  }
  if (obj !== null && typeof obj === 'object' && !(obj instanceof Date) && !(obj instanceof File) && !(obj instanceof Blob)) {
    return Object.keys(obj).reduce((result, key) => {
      const camelKey = snakeToCamel(key)
      result[camelKey] = convertKeysToCamel(obj[key])
      return result
    }, {})
  }
  return obj
}

function convertKeysToSnake(obj) {
  if (Array.isArray(obj)) {
    return obj.map(item => convertKeysToSnake(item))
  }
  if (obj !== null && typeof obj === 'object' && !(obj instanceof Date) && !(obj instanceof File) && !(obj instanceof Blob) && !(obj instanceof FormData)) {
    return Object.keys(obj).reduce((result, key) => {
      const snakeKey = camelToSnake(key)
      result[snakeKey] = convertKeysToSnake(obj[key])
      return result
    }, {})
  }
  return obj
}

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Queue for failed requests during token refresh
let failedQueue = []

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

// Request interceptor - add auth token and convert keys to snake_case
apiClient.interceptors.request.use(
  (config) => {
    // Always get token from localStorage - it's the source of truth
    // This avoids issues with Pinia not being initialized during some requests
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // Convert request body keys to snake_case (skip FormData)
    if (config.data && !(config.data instanceof FormData)) {
      config.data = convertKeysToSnake(config.data)
    }

    // Convert query params keys to snake_case
    if (config.params) {
      config.params = convertKeysToSnake(config.params)
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle errors, auto-refresh token, and convert keys to camelCase
apiClient.interceptors.response.use(
  (response) => {
    // Convert response data keys to camelCase (skip blob responses)
    if (response.data && !(response.data instanceof Blob)) {
      response.data = convertKeysToCamel(response.data)
    }
    return response
  },
  async (error) => {
    const authStore = useAuthStore()
    const originalRequest = error.config

    if (error.response) {
      const { status, data } = error.response

      // Handle 401 Unauthorized - try to refresh token
      if (status === 401 && !originalRequest._retry) {
        // Don't retry refresh endpoint itself
        if (originalRequest.url === '/auth/refresh') {
          authStore.logout()
          router.push('/login')
          return Promise.reject(error)
        }

        // If already refreshing, queue the request
        if (authStore.isRefreshing) {
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject })
          }).then(token => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            return apiClient(originalRequest)
          }).catch(err => {
            return Promise.reject(err)
          })
        }

        originalRequest._retry = true

        // Try to refresh token
        const refreshed = await authStore.refreshAccessToken()

        if (refreshed) {
          // Retry original request with new token
          processQueue(null, authStore.token)
          originalRequest.headers.Authorization = `Bearer ${authStore.token}`
          return apiClient(originalRequest)
        } else {
          // Refresh failed, redirect to login
          processQueue(error, null)
          router.push('/login')
          return Promise.reject(error)
        }
      }

      // Handle 403 Forbidden
      if (status === 403) {
        console.error('Access forbidden:', data.detail || 'Permission denied')
      }

      // Handle validation errors
      if (status === 422) {
        const validationErrors = data.detail || []
        console.error('Validation errors:', validationErrors)
      }

      // Handle server errors
      if (status >= 500) {
        console.error('Server error:', data.detail || 'An unexpected error occurred')
      }

      // Return error message from API if available
      error.message = data.detail || data.message || error.message
    } else if (error.request) {
      error.message = 'Network error. Please check your connection.'
    }

    return Promise.reject(error)
  }
)

export default apiClient
