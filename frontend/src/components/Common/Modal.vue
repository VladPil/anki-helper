<script setup>
import { watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md', 'lg', 'xl'].includes(value)
  },
  closable: {
    type: Boolean,
    default: true
  },
  closeOnBackdrop: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue', 'close'])

function close() {
  if (props.closable) {
    emit('update:modelValue', false)
    emit('close')
  }
}

function handleBackdropClick() {
  if (props.closeOnBackdrop) {
    close()
  }
}

function handleEscape(e) {
  if (e.key === 'Escape' && props.modelValue && props.closable) {
    close()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleEscape)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscape)
})

// Prevent body scroll when modal is open
watch(() => props.modelValue, (isOpen) => {
  if (isOpen) {
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
})

const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl'
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="modal modal-open"
      @click.self="handleBackdropClick"
    >
      <div class="modal-box" :class="sizeClasses[size]">
        <!-- Header -->
        <div v-if="title || closable" class="flex items-center justify-between mb-4">
          <h3 v-if="title" class="font-bold text-lg">{{ title }}</h3>
          <button
            v-if="closable"
            @click="close"
            class="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Content -->
        <div class="modal-content">
          <slot />
        </div>

        <!-- Footer slot -->
        <div v-if="$slots.footer" class="modal-action mt-4">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
