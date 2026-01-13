import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { useLocalStorage } from '@vueuse/core'

export const useUiStore = defineStore('ui', () => {
  // Theme - persisted to localStorage
  const theme = useLocalStorage('theme', 'light')

  // Sidebar state
  const sidebarOpen = ref(true)
  const sidebarCollapsed = useLocalStorage('sidebarCollapsed', false)

  // Modal state
  const activeModal = ref(null)
  const modalData = ref(null)

  // Notifications
  const notifications = ref([])
  let notificationId = 0

  // Loading states
  const globalLoading = ref(false)
  const loadingMessage = ref('')

  // Mobile detection
  const isMobile = ref(window.innerWidth < 768)

  // Watch for window resize
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', () => {
      isMobile.value = window.innerWidth < 768
      if (isMobile.value) {
        sidebarOpen.value = false
      }
    })
  }

  // Theme management
  function setTheme(newTheme) {
    theme.value = newTheme
    document.documentElement.setAttribute('data-theme', newTheme)
  }

  function toggleTheme() {
    setTheme(theme.value === 'light' ? 'dark' : 'light')
  }

  // Initialize theme on load
  function initTheme() {
    // Check system preference if no saved preference
    if (!localStorage.getItem('theme')) {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      theme.value = prefersDark ? 'dark' : 'light'
    }
    document.documentElement.setAttribute('data-theme', theme.value)
  }

  // Sidebar management
  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }

  function openSidebar() {
    sidebarOpen.value = true
  }

  function closeSidebar() {
    sidebarOpen.value = false
  }

  function toggleSidebarCollapse() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  // Modal management
  function openModal(name, data = null) {
    activeModal.value = name
    modalData.value = data
  }

  function closeModal() {
    activeModal.value = null
    modalData.value = null
  }

  function isModalOpen(name) {
    return activeModal.value === name
  }

  // Notification management
  function addNotification(notification) {
    const id = ++notificationId
    const newNotification = {
      id,
      type: notification.type || 'info',
      message: notification.message,
      duration: notification.duration ?? 5000
    }

    notifications.value.push(newNotification)

    // Auto-remove after duration
    if (newNotification.duration > 0) {
      setTimeout(() => {
        removeNotification(id)
      }, newNotification.duration)
    }

    return id
  }

  function removeNotification(id) {
    notifications.value = notifications.value.filter(n => n.id !== id)
  }

  function clearNotifications() {
    notifications.value = []
  }

  // Convenience notification methods
  function notify(message, type = 'info', duration) {
    return addNotification({ message, type, duration })
  }

  function notifySuccess(message, duration) {
    return addNotification({ message, type: 'success', duration })
  }

  function notifyError(message, duration = 8000) {
    return addNotification({ message, type: 'error', duration })
  }

  function notifyWarning(message, duration) {
    return addNotification({ message, type: 'warning', duration })
  }

  function notifyInfo(message, duration) {
    return addNotification({ message, type: 'info', duration })
  }

  // Global loading
  function setGlobalLoading(loading, message = '') {
    globalLoading.value = loading
    loadingMessage.value = message
  }

  function startLoading(message = 'Loading...') {
    setGlobalLoading(true, message)
  }

  function stopLoading() {
    setGlobalLoading(false, '')
  }

  return {
    // State
    theme,
    sidebarOpen,
    sidebarCollapsed,
    activeModal,
    modalData,
    notifications,
    globalLoading,
    loadingMessage,
    isMobile,
    // Theme actions
    setTheme,
    toggleTheme,
    initTheme,
    // Sidebar actions
    toggleSidebar,
    openSidebar,
    closeSidebar,
    toggleSidebarCollapse,
    // Modal actions
    openModal,
    closeModal,
    isModalOpen,
    // Notification actions
    addNotification,
    removeNotification,
    clearNotifications,
    notify,
    notifySuccess,
    notifyError,
    notifyWarning,
    notifyInfo,
    // Loading actions
    setGlobalLoading,
    startLoading,
    stopLoading
  }
})
