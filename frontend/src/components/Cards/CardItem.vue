<script setup>
import { ref } from 'vue'

const props = defineProps({
  card: {
    type: Object,
    required: true
  },
  selectable: {
    type: Boolean,
    default: false
  },
  selected: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['edit', 'delete', 'toggle-select'])

const isFlipped = ref(false)

function toggleFlip() {
  isFlipped.value = !isFlipped.value
}

function truncate(text, length = 100) {
  if (!text) return ''
  return text.length > length ? text.substring(0, length) + '...' : text
}
</script>

<template>
  <div
    class="card bg-base-100 shadow-md hover:shadow-lg transition-shadow cursor-pointer"
    :class="{ 'ring-2 ring-primary': selected }"
    @click="toggleFlip"
  >
    <div class="card-body p-4">
      <!-- Header with checkbox and actions -->
      <div class="flex items-start justify-between mb-2">
        <div v-if="selectable" class="flex items-center" @click.stop>
          <input
            type="checkbox"
            :checked="selected"
            @change="emit('toggle-select')"
            class="checkbox checkbox-primary checkbox-sm"
          />
        </div>

        <div class="flex gap-1" @click.stop>
          <button
            @click="emit('edit')"
            class="btn btn-ghost btn-xs"
            title="Edit card"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button
            @click="emit('delete')"
            class="btn btn-ghost btn-xs text-error"
            title="Delete card"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Card content -->
      <div class="card-flip" :class="{ 'flipped': isFlipped }">
        <div class="relative min-h-[100px]">
          <!-- Front -->
          <div
            class="card-flip-front absolute inset-0"
            :class="{ 'invisible': isFlipped }"
          >
            <div class="badge badge-outline badge-sm mb-2">Front</div>
            <p class="text-base-content">{{ truncate(card.front, 150) }}</p>
          </div>

          <!-- Back -->
          <div
            class="card-flip-back absolute inset-0"
            :class="{ 'invisible': !isFlipped }"
          >
            <div class="badge badge-outline badge-sm mb-2">Back</div>
            <p class="text-base-content">{{ truncate(card.back, 150) }}</p>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-between mt-4 pt-2 border-t border-base-200">
        <div class="flex gap-1">
          <span
            v-for="tag in (card.tags || []).slice(0, 3)"
            :key="tag"
            class="badge badge-ghost badge-xs"
          >
            {{ tag }}
          </span>
        </div>
        <span class="text-xs text-base-content/50">
          Click to {{ isFlipped ? 'show front' : 'flip' }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card-flip {
  perspective: 1000px;
}

.card-flip-front,
.card-flip-back {
  transition: opacity 0.3s ease;
}
</style>
