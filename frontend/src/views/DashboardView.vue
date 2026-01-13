<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useDecksStore } from '@/stores/decks'
import { useCardsStore } from '@/stores/cards'
import { useAuthStore } from '@/stores/auth'
import LoadingSpinner from '@/components/Common/LoadingSpinner.vue'
import Button from '@/components/Common/Button.vue'

const router = useRouter()
const decksStore = useDecksStore()
const cardsStore = useCardsStore()
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

function navigateTo(path) {
  router.push(path)
}
</script>

<template>
  <div class="container mx-auto max-w-7xl">
    <!-- Welcome Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-base-content">
        Welcome back, {{ authStore.userName }}
      </h1>
      <p class="text-base-content/70 mt-2">
        Here's an overview of your learning progress
      </p>
    </div>

    <LoadingSpinner v-if="loading" class="py-12" />

    <template v-else>
      <!-- Stats Cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div class="stat bg-base-100 rounded-box shadow">
          <div class="stat-figure text-primary">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="w-8 h-8 stroke-current">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <div class="stat-title">Total Decks</div>
          <div class="stat-value text-primary">{{ stats.totalDecks }}</div>
        </div>

        <div class="stat bg-base-100 rounded-box shadow">
          <div class="stat-figure text-secondary">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="w-8 h-8 stroke-current">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div class="stat-title">Total Cards</div>
          <div class="stat-value text-secondary">{{ stats.totalCards }}</div>
        </div>

        <div class="stat bg-base-100 rounded-box shadow">
          <div class="stat-figure text-accent">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="w-8 h-8 stroke-current">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="stat-title">Due Today</div>
          <div class="stat-value text-accent">{{ stats.dueCards }}</div>
        </div>

        <div class="stat bg-base-100 rounded-box shadow">
          <div class="stat-figure text-success">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="w-8 h-8 stroke-current">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="stat-title">Reviews Today</div>
          <div class="stat-value text-success">{{ stats.reviewsToday }}</div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div class="card bg-base-100 shadow-lg">
          <div class="card-body">
            <h2 class="card-title">Quick Actions</h2>
            <div class="flex flex-wrap gap-3 mt-4">
              <Button @click="navigateTo('/generate')" variant="primary">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Generate Cards
              </Button>
              <Button @click="navigateTo('/chat')" variant="secondary">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                AI Chat
              </Button>
              <Button @click="navigateTo('/decks')" variant="ghost">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                New Deck
              </Button>
            </div>
          </div>
        </div>

        <div class="card bg-gradient-to-br from-primary to-secondary text-primary-content shadow-lg">
          <div class="card-body">
            <h2 class="card-title">Start Learning</h2>
            <p class="opacity-90">Review your due cards and improve your knowledge retention.</p>
            <div class="card-actions justify-end mt-4">
              <Button variant="ghost" class="bg-white/20 hover:bg-white/30 border-none text-white">
                Start Review Session
              </Button>
            </div>
          </div>
        </div>
      </div>

      <!-- Recent Decks -->
      <div class="card bg-base-100 shadow-lg">
        <div class="card-body">
          <div class="flex justify-between items-center mb-4">
            <h2 class="card-title">Recent Decks</h2>
            <Button @click="navigateTo('/decks')" variant="ghost" size="sm">
              View All
            </Button>
          </div>

          <div v-if="recentDecks.length === 0" class="text-center py-8 text-base-content/60">
            <p>No decks yet. Create your first deck to get started!</p>
            <Button @click="navigateTo('/decks')" variant="primary" class="mt-4">
              Create Deck
            </Button>
          </div>

          <div v-else class="overflow-x-auto">
            <table class="table table-zebra">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Cards</th>
                  <th>Due</th>
                  <th>Last Updated</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="deck in recentDecks" :key="deck.id" class="hover cursor-pointer" @click="navigateTo(`/decks/${deck.id}`)">
                  <td class="font-medium">{{ deck.name }}</td>
                  <td>{{ deck.cardCount || 0 }}</td>
                  <td>
                    <span class="badge badge-accent badge-sm">{{ deck.dueCount || 0 }}</span>
                  </td>
                  <td class="text-base-content/60">
                    {{ new Date(deck.updatedAt).toLocaleDateString() }}
                  </td>
                  <td>
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-base-content/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
