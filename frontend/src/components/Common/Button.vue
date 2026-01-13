<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (value) => ['primary', 'secondary', 'accent', 'ghost', 'link', 'info', 'success', 'warning', 'error'].includes(value)
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['xs', 'sm', 'md', 'lg'].includes(value)
  },
  loading: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  },
  outline: {
    type: Boolean,
    default: false
  },
  block: {
    type: Boolean,
    default: false
  }
})

const buttonClass = computed(() => {
  const classes = ['btn']

  // Variant
  if (props.outline) {
    classes.push(`btn-outline`)
  }
  classes.push(`btn-${props.variant}`)

  // Size
  if (props.size !== 'md') {
    classes.push(`btn-${props.size}`)
  }

  // Block
  if (props.block) {
    classes.push('btn-block')
  }

  // Loading
  if (props.loading) {
    classes.push('loading')
  }

  return classes.join(' ')
})

const isDisabled = computed(() => props.disabled || props.loading)
</script>

<template>
  <button :class="buttonClass" :disabled="isDisabled">
    <span v-if="loading" class="loading loading-spinner loading-sm mr-2"></span>
    <slot />
  </button>
</template>
