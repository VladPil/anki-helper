<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  deck: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['edit', 'delete'])

const router = useRouter()

const cardCount = computed(() => props.deck.cardCount || 0)
const dueCount = computed(() => props.deck.dueCount || 0)

function navigateToDeck() {
  router.push(`/decks/${props.deck.id}`)
}

function formatDate(dateString) {
  if (!dateString) return ''
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}
</script>

<template>
  <div
    class="card bg-base-100 shadow-md hover:shadow-lg transition-all cursor-pointer"
    @click="navigateToDeck"
  >
    <div class="card-body">
      <!-- Header -->
      <div class="flex items-start justify-between">
        <div>
          <h2 class="card-title text-lg">{{ deck.name }}</h2>
          <p v-if="deck.description" class="text-sm text-base-content/60 mt-1 line-clamp-2">
            {{ deck.description }}
          </p>
        </div>

        <!-- Dropdown menu -->
        <div class="dropdown dropdown-end" @click.stop>
          <label tabindex="0" class="btn btn-ghost btn-sm btn-circle">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
            </svg>
          </label>
          <ul tabindex="0" class="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-40">
            <li><a @click="emit('edit')">Edit</a></li>
            <li><a @click="emit('delete')" class="text-error">Delete</a></li>
          </ul>
        </div>
      </div>

      <!-- Stats -->
      <div class="flex gap-4 mt-4">
        <div class="stat-item">
          <span class="text-2xl font-bold text-primary">{{ cardCount }}</span>
          <span class="text-xs text-base-content/60 block">Cards</span>
        </div>
        <div class="stat-item">
          <span class="text-2xl font-bold" :class="dueCount > 0 ? 'text-accent' : 'text-base-content/50'">
            {{ dueCount }}
          </span>
          <span class="text-xs text-base-content/60 block">Due</span>
        </div>
      </div>

      <!-- Tags -->
      <div v-if="deck.tags && deck.tags.length > 0" class="flex flex-wrap gap-1 mt-3">
        <span
          v-for="tag in deck.tags.slice(0, 3)"
          :key="tag"
          class="badge badge-ghost badge-sm"
        >
          {{ tag }}
        </span>
        <span v-if="deck.tags.length > 3" class="badge badge-ghost badge-sm">
          +{{ deck.tags.length - 3 }}
        </span>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-between mt-4 pt-3 border-t border-base-200">
        <span class="text-xs text-base-content/50">
          Updated {{ formatDate(deck.updatedAt) }}
        </span>
        <div class="flex gap-2">
          <button
            v-if="dueCount > 0"
            class="btn btn-primary btn-sm"
            @click.stop
          >
            Study
          </button>
          <button
            class="btn btn-ghost btn-sm"
            @click.stop="navigateToDeck"
          >
            View
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stat-item {
  @apply flex flex-col;
}
</style>
