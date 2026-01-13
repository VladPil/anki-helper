<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUiStore } from '@/stores/ui'
import { useDecksStore } from '@/stores/decks'

const route = useRoute()
const uiStore = useUiStore()
const decksStore = useDecksStore()

const isOpen = computed(() => uiStore.sidebarOpen)

// Use recent decks from localStorage, fallback to sorted decks
const recentDecksToShow = computed(() => {
  // If we have recent decks in localStorage, use them
  if (decksStore.recentDecks.length > 0) {
    return decksStore.recentDecks.slice(0, 5)
  }
  // Otherwise fallback to sorted decks
  return decksStore.sortedDecks.slice(0, 5)
})

const navItems = [
  {
    name: 'Главная',
    path: '/',
    icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6'
  },
  {
    name: 'Мои колоды',
    path: '/decks',
    icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10'
  },
  {
    name: 'Генерация карточек',
    path: '/generate',
    icon: 'M13 10V3L4 14h7v7l9-11h-7z'
  },
  {
    name: 'ИИ-чат',
    path: '/chat',
    icon: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z'
  },
  {
    name: 'Настройки',
    path: '/settings',
    icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z'
  }
]

function isActiveRoute(path) {
  if (path === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(path)
}

function closeSidebar() {
  if (uiStore.isMobile) {
    uiStore.closeSidebar()
  }
}
</script>

<template>
  <!-- Overlay for mobile -->
  <div
    v-if="isOpen && uiStore.isMobile"
    class="fixed inset-0 bg-black/50 z-30 lg:hidden"
    @click="closeSidebar"
  ></div>

  <!-- Sidebar -->
  <aside
    class="fixed top-16 left-0 z-40 h-[calc(100vh-4rem)] w-64 bg-base-100 border-r border-base-200 transition-transform duration-300 overflow-y-auto"
    :class="{
      '-translate-x-full': !isOpen,
      'translate-x-0': isOpen
    }"
  >
    <nav class="p-4">
      <!-- Main navigation -->
      <ul class="menu menu-lg p-0 gap-1">
        <li v-for="item in navItems" :key="item.path">
          <router-link
            :to="item.path"
            :class="{ 'active': isActiveRoute(item.path) }"
            @click="closeSidebar"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                :d="item.icon"
              />
            </svg>
            {{ item.name }}
          </router-link>
        </li>
      </ul>

      <!-- Divider -->
      <div class="divider my-4">Недавние колоды</div>

      <!-- Recent decks - persisted to localStorage -->
      <ul class="menu menu-sm p-0 gap-1">
        <li v-if="recentDecksToShow.length === 0">
          <span class="text-base-content/50 italic">Пока нет колод</span>
        </li>
        <li v-for="deck in recentDecksToShow" :key="deck.id">
          <router-link
            :to="`/decks/${deck.id}`"
            :class="{ 'active': route.params.id === deck.id }"
            @click="closeSidebar"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span class="truncate">{{ deck.name }}</span>
            <span class="badge badge-sm badge-ghost">{{ deck.cardCount || 0 }}</span>
          </router-link>
        </li>
      </ul>

      <!-- Quick stats -->
      <div class="mt-6 p-4 bg-base-200 rounded-lg">
        <h3 class="font-semibold text-sm mb-2">Статистика</h3>
        <div class="flex justify-between text-sm">
          <span class="text-base-content/70">Всего колод</span>
          <span class="font-medium">{{ decksStore.deckCount }}</span>
        </div>
        <div class="flex justify-between text-sm">
          <span class="text-base-content/70">Всего карточек</span>
          <span class="font-medium">{{ decksStore.totalCards }}</span>
        </div>
      </div>
    </nav>
  </aside>
</template>
