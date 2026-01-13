<script setup>
import Button from '@/components/Common/Button.vue'

defineProps({
  status: {
    type: String,
    default: 'idle',
    validator: (value) => ['idle', 'processing', 'complete', 'error'].includes(value)
  },
  message: {
    type: String,
    default: ''
  },
  progress: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['cancel'])
</script>

<template>
  <div class="card bg-base-100 shadow-lg">
    <div class="card-body items-center text-center py-12">
      <!-- Loading animation -->
      <div class="relative mb-6">
        <div
          class="radial-progress text-primary"
          :style="`--value:${progress}; --size:8rem; --thickness:4px;`"
          role="progressbar"
        >
          <div v-if="status === 'processing'" class="absolute inset-0 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 text-primary animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div v-else-if="status === 'complete'" class="absolute inset-0 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div v-else-if="status === 'error'" class="absolute inset-0 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 text-error" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
        </div>
      </div>

      <!-- Status message -->
      <h2 class="text-xl font-semibold mb-2">
        <template v-if="status === 'processing'">Generating Cards...</template>
        <template v-else-if="status === 'complete'">Generation Complete!</template>
        <template v-else-if="status === 'error'">Generation Failed</template>
        <template v-else>Ready to Generate</template>
      </h2>

      <p class="text-base-content/70 mb-6">{{ message }}</p>

      <!-- Progress bar -->
      <div v-if="status === 'processing'" class="w-full max-w-md mb-6">
        <progress class="progress progress-primary w-full" :value="progress" max="100"></progress>
        <p class="text-sm text-base-content/60 mt-2">{{ progress }}% complete</p>
      </div>

      <!-- Tips while generating -->
      <div v-if="status === 'processing'" class="alert alert-info max-w-md">
        <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>AI is analyzing your content and creating high-quality flashcards. This may take a minute.</span>
      </div>

      <!-- Cancel button -->
      <div v-if="status === 'processing'" class="mt-6">
        <Button @click="emit('cancel')" variant="ghost">
          Cancel
        </Button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.radial-progress {
  display: inline-grid;
  place-content: center;
  position: relative;
  vertical-align: middle;
  box-sizing: content-box;
  width: var(--size);
  height: var(--size);
  border-radius: 50%;
  background-color: transparent;
}

.radial-progress::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: conic-gradient(currentColor calc(var(--value) * 1%), transparent 0);
  mask: radial-gradient(farthest-side, transparent calc(100% - var(--thickness)), #000 calc(100% - var(--thickness) + 1px));
}

.radial-progress::after {
  content: "";
  position: absolute;
  inset: var(--thickness);
  border-radius: inherit;
  background: hsl(var(--b2));
}
</style>
