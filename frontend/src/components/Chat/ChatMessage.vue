<script setup>
import { computed } from 'vue'

const props = defineProps({
  message: {
    type: Object,
    required: true
  },
  isStreaming: {
    type: Boolean,
    default: false
  }
})

const isUser = computed(() => props.message.role === 'user')
const isAssistant = computed(() => props.message.role === 'assistant')

const formattedTime = computed(() => {
  if (!props.message.timestamp) return ''
  return new Date(props.message.timestamp).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit'
  })
})

// Simple markdown-like rendering for code blocks
const formattedContent = computed(() => {
  let content = props.message.content || ''

  // Handle code blocks
  content = content.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre class="bg-base-300 rounded-lg p-3 my-2 overflow-x-auto"><code class="text-sm">${escapeHtml(code.trim())}</code></pre>`
  })

  // Handle inline code
  content = content.replace(/`([^`]+)`/g, '<code class="bg-base-300 px-1 rounded text-sm">$1</code>')

  // Handle bold
  content = content.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')

  // Handle line breaks
  content = content.replace(/\n/g, '<br>')

  return content
})

function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  }
  return text.replace(/[&<>"']/g, m => map[m])
}
</script>

<template>
  <div
    class="flex gap-3"
    :class="{ 'flex-row-reverse': isUser }"
  >
    <!-- Avatar -->
    <div class="flex-shrink-0">
      <div
        v-if="isUser"
        class="avatar placeholder"
      >
        <div class="bg-primary text-primary-content rounded-full w-8">
          <span class="text-sm">U</span>
        </div>
      </div>
      <div
        v-else
        class="avatar placeholder"
      >
        <div class="bg-secondary text-secondary-content rounded-full w-8">
          <span class="text-sm">AI</span>
        </div>
      </div>
    </div>

    <!-- Message bubble -->
    <div
      class="flex-1 max-w-[80%]"
      :class="{ 'text-right': isUser }"
    >
      <div
        class="inline-block rounded-lg px-4 py-2 text-left"
        :class="{
          'bg-primary text-primary-content': isUser,
          'bg-base-200': isAssistant
        }"
      >
        <div
          v-html="formattedContent"
          class="prose prose-sm max-w-none"
          :class="{
            'prose-invert': isUser
          }"
        ></div>

        <!-- Streaming cursor -->
        <span
          v-if="isStreaming"
          class="inline-block w-2 h-4 bg-current animate-pulse ml-1"
        ></span>
      </div>

      <!-- Timestamp -->
      <div
        class="text-xs text-base-content/50 mt-1"
        :class="{ 'text-right': isUser }"
      >
        {{ formattedTime }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.prose :deep(pre) {
  margin: 0.5rem 0;
}

.prose :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.prose-invert :deep(code) {
  background: rgba(255, 255, 255, 0.2);
}
</style>
