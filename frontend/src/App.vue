<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import Navbar from '@/components/Layout/Navbar.vue'
import Sidebar from '@/components/Layout/Sidebar.vue'
import Footer from '@/components/Layout/Footer.vue'
import Alert from '@/components/Common/Alert.vue'

const route = useRoute()
const authStore = useAuthStore()
const uiStore = useUiStore()

const isAuthPage = computed(() => {
  return ['/login', '/register'].includes(route.path)
})

const showSidebar = computed(() => {
  return authStore.isAuthenticated && !isAuthPage.value && uiStore.sidebarOpen
})
</script>

<template>
  <div class="min-h-screen flex flex-col" :data-theme="uiStore.theme">
    <!-- Notifications -->
    <div class="toast toast-top toast-end z-50">
      <Alert
        v-for="notification in uiStore.notifications"
        :key="notification.id"
        :type="notification.type"
        :message="notification.message"
        :dismissible="true"
        @dismiss="uiStore.removeNotification(notification.id)"
      />
    </div>

    <!-- Auth pages layout -->
    <template v-if="isAuthPage">
      <main class="flex-1 flex items-center justify-center p-4">
        <router-view />
      </main>
    </template>

    <!-- Main app layout -->
    <template v-else>
      <Navbar />
      <div class="flex flex-1">
        <Sidebar v-if="authStore.isAuthenticated" />
        <main
          class="flex-1 p-4 md:p-6 lg:p-8 transition-all duration-300"
          :class="{ 'lg:ml-64': showSidebar }"
        >
          <router-view />
        </main>
      </div>
      <Footer />
    </template>
  </div>
</template>

<style scoped>
</style>
