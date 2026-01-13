import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor - add auth token
apiClient.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle errors
apiClient.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    const authStore = useAuthStore()

    if (error.response) {
      const { status, data } = error.response

      // Handle 401 Unauthorized - redirect to login
      if (status === 401) {
        authStore.logout()
        router.push('/login')
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
