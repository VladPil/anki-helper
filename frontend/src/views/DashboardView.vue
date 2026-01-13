<script setup>
import { ref, onMounted, computed } from 'vue'
import { useDecksStore } from '@/stores/decks'
import { useAuthStore } from '@/stores/auth'
import LoadingSpinner from '@/components/Common/LoadingSpinner.vue'
import StatsCards from '@/components/Dashboard/StatsCards.vue'
import QuickActions from '@/components/Dashboard/QuickActions.vue'
import RecentDecksTable from '@/components/Dashboard/RecentDecksTable.vue'

const decksStore = useDecksStore()
const authStore = useAuthStore()

const loading = ref(true)
const stats = ref({
  totalDecks: 0,
  totalCards: 0,
  dueCards: 0,
  reviewsToday: 0
})

const recentDecks = computed(() => decksStore.sortedDecks.slice(0, 5))

onMounted(async () => {
  try {
    await decksStore.fetchDecks()
    stats.value.totalDecks = decksStore.deckCount
    stats.value.totalCards = decksStore.totalCards
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="container mx-auto max-w-7xl">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-base-content">
        С возвращением, {{ authStore.userName }}
      </h1>
      <p class="text-base-content/70 mt-2">
        Обзор вашего прогресса в обучении
      </p>
    </div>

    <LoadingSpinner v-if="loading" class="py-12" />

    <template v-else>
      <StatsCards :stats="stats" />
      <QuickActions />
      <RecentDecksTable :decks="recentDecks" />
    </template>
  </div>
</template>
