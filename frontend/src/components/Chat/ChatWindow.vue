<script setup>
import { ref, watch, nextTick } from 'vue'
import ChatMessage from './ChatMessage.vue'
import LoadingSpinner from '@/components/Common/LoadingSpinner.vue'

const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  },
  isLoading: {
    type: Boolean,
    default: false
  },
  isStreaming: {
    type: Boolean,
    default: false
  }
})

const messagesContainer = ref(null)

// Scroll to bottom when new messages arrive
watch(() => props.messages.length, async () => {
  await nextTick()
  scrollToBottom()
})

watch(() => props.messages[props.messages.length - 1]?.content, async () => {
  await nextTick()
  scrollToBottom()
})

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}
</script>

<template>
  <div
    ref="messagesContainer"
    class="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin"
  >
    <!-- Empty state -->
    <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-center">
      <div class="w-16 h-16 mb-4 rounded-full bg-primary/10 flex items-center justify-center">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
      </div>
      <h3 class="text-lg font-semibold mb-2">Start a conversation</h3>
      <p class="text-base-content/60 max-w-md">
        Ask questions about your study materials, get explanations, or request help with creating flashcards.
      </p>

      <!-- Suggested prompts -->
      <div class="mt-6 flex flex-wrap gap-2 justify-center max-w-lg">
        <span class="badge badge-outline badge-lg cursor-pointer hover:badge-primary">
          Explain this concept to me
        </span>
        <span class="badge badge-outline badge-lg cursor-pointer hover:badge-primary">
          Help me understand my cards
        </span>
        <span class="badge badge-outline badge-lg cursor-pointer hover:badge-primary">
          Create practice questions
        </span>
      </div>
    </div>

    <!-- Messages -->
    <ChatMessage
      v-for="(message, index) in messages"
      :key="message.id || index"
      :message="message"
      :isStreaming="isStreaming && index === messages.length - 1 && message.role === 'assistant'"
    />

    <!-- Loading indicator -->
    <div v-if="isLoading && !isStreaming" class="flex justify-start">
      <div class="bg-base-200 rounded-lg px-4 py-3">
        <div class="flex items-center gap-2">
          <span class="loading loading-dots loading-sm"></span>
          <span class="text-sm text-base-content/70">AI is thinking...</span>
        </div>
      </div>
    </div>
  </div>
</template>
