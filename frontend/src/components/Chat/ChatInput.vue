<script setup>
import { ref } from 'vue'

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false
  },
  placeholder: {
    type: String,
    default: 'Type your message...'
  }
})

const emit = defineEmits(['send'])

const message = ref('')
const textareaRef = ref(null)

function handleSubmit() {
  if (!message.value.trim() || props.disabled) return

  emit('send', message.value)
  message.value = ''

  // Reset textarea height
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
  }
}

function handleKeydown(e) {
  // Submit on Enter (without Shift)
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSubmit()
  }
}

function autoResize(e) {
  const textarea = e.target
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
}
</script>

<template>
  <div class="p-4 border-t border-base-200 bg-base-100">
    <form @submit.prevent="handleSubmit" class="flex gap-2 items-end">
      <div class="flex-1 relative">
        <textarea
          ref="textareaRef"
          v-model="message"
          :placeholder="placeholder"
          :disabled="disabled"
          @keydown="handleKeydown"
          @input="autoResize"
          class="textarea textarea-bordered w-full min-h-[48px] max-h-[200px] resize-none pr-12"
          rows="1"
        ></textarea>

        <!-- Character count (optional) -->
        <div v-if="message.length > 0" class="absolute bottom-2 right-2 text-xs text-base-content/40">
          {{ message.length }}
        </div>
      </div>

      <button
        type="submit"
        class="btn btn-primary btn-circle"
        :disabled="!message.trim() || disabled"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
        </svg>
      </button>
    </form>

    <p class="text-xs text-base-content/50 mt-2 text-center">
      Press Enter to send, Shift+Enter for new line
    </p>
  </div>
</template>
