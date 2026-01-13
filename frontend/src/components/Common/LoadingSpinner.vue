<script setup>
const props = defineProps({
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['xs', 'sm', 'md', 'lg'].includes(value)
  },
  text: {
    type: String,
    default: ''
  }
})

const sizeClasses = {
  xs: 'loading-xs',
  sm: 'loading-sm',
  md: 'loading-md',
  lg: 'loading-lg'
}
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-2">
    <span class="loading loading-spinner text-primary" :class="sizeClasses[size]"></span>
    <span v-if="text" class="text-base-content/70">{{ text }}</span>
  </div>
</template>
