<script setup>
import { ref } from 'vue'

const props = defineProps({
  card: {
    type: Object,
    required: true
  },
  showActions: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['edit', 'delete', 'select', 'deselect'])

const isFlipped = ref(false)

function toggleFlip() {
  isFlipped.value = !isFlipped.value
}
</script>

<template>
  <div class="card bg-base-100 shadow-lg h-64 cursor-pointer" @click="toggleFlip">
    <div class="card-body flex flex-col h-full p-6">
      <!-- Card content with flip effect -->
      <div class="flex-1 flex items-center justify-center overflow-auto">
        <div class="text-center">
          <div v-if="!isFlipped">
            <span class="badge badge-outline badge-sm mb-3">Question</span>
            <p class="text-lg font-medium whitespace-pre-wrap">{{ card.front }}</p>
          </div>
          <div v-else>
            <span class="badge badge-primary badge-sm mb-3">Answer</span>
            <p class="text-lg whitespace-pre-wrap">{{ card.back }}</p>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-between pt-4 border-t border-base-200">
        <div class="flex gap-1">
          <span
            v-for="tag in (card.tags || []).slice(0, 2)"
            :key="tag"
            class="badge badge-ghost badge-sm"
          >
            {{ tag }}
          </span>
          <span v-if="(card.tags || []).length > 2" class="badge badge-ghost badge-sm">
            +{{ card.tags.length - 2 }}
          </span>
        </div>

        <div v-if="showActions" class="flex gap-1" @click.stop>
          <button
            @click="emit('edit')"
            class="btn btn-ghost btn-xs"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button
            @click="emit('delete')"
            class="btn btn-ghost btn-xs text-error"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
        <span v-else class="text-xs text-base-content/50">
          Click to flip
        </span>
      </div>
    </div>
  </div>
</template>
