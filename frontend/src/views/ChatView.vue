<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { useDecksStore } from '@/stores/decks'
import { useUiStore } from '@/stores/ui'
import { chatApi } from '@/api/chat'
import ChatWindow from '@/components/Chat/ChatWindow.vue'
import ChatInput from '@/components/Chat/ChatInput.vue'
import Button from '@/components/Common/Button.vue'

const decksStore = useDecksStore()
const uiStore = useUiStore()

const messages = ref([])
const conversations = ref([])
const currentConversationId = ref(null)
const isLoading = ref(false)
const isStreaming = ref(false)
const selectedDeckId = ref(null)
const showConversationList = ref(false)

const currentConversation = computed(() =>
  conversations.value.find(c => c.id === currentConversationId.value)
)

onMounted(async () => {
  await Promise.all([
    decksStore.fetchDecks(),
    loadConversations()
  ])
})

async function loadConversations() {
  try {
    const response = await chatApi.getConversations({ limit: 20 })
    conversations.value = response.conversations || response || []
  } catch (error) {
    console.error('Failed to load conversations:', error)
  }
}

async function startNewConversation() {
  currentConversationId.value = null
  messages.value = []
  showConversationList.value = false
}

async function loadConversation(conversationId) {
  try {
    const conversation = await chatApi.getConversation(conversationId)
    currentConversationId.value = conversationId
    messages.value = conversation.messages || []
    showConversationList.value = false
  } catch (error) {
    uiStore.notifyError('Failed to load conversation')
  }
}

async function deleteConversation(conversationId) {
  if (!confirm('Delete this conversation?')) return

  try {
    await chatApi.deleteConversation(conversationId)
    conversations.value = conversations.value.filter(c => c.id !== conversationId)

    if (currentConversationId.value === conversationId) {
      startNewConversation()
    }

    uiStore.notifySuccess('Conversation deleted')
  } catch (error) {
    uiStore.notifyError('Failed to delete conversation')
  }
}

async function sendMessage(content) {
  if (!content.trim() || isLoading.value) return

  // Add user message
  const userMessage = {
    id: Date.now().toString(),
    role: 'user',
    content: content.trim(),
    timestamp: new Date().toISOString()
  }
  messages.value.push(userMessage)

  isLoading.value = true
  isStreaming.value = true

  // Add placeholder for assistant message
  const assistantMessage = {
    id: (Date.now() + 1).toString(),
    role: 'assistant',
    content: '',
    timestamp: new Date().toISOString()
  }
  messages.value.push(assistantMessage)

  try {
    await chatApi.sendMessageStream(
      {
        message: content.trim(),
        conversationId: currentConversationId.value,
        deckId: selectedDeckId.value
      },
      // On chunk
      (chunk) => {
        const lastMessage = messages.value[messages.value.length - 1]
        if (lastMessage.role === 'assistant') {
          lastMessage.content += chunk.content || chunk.delta || ''
        }
      },
      // On complete
      async () => {
        isStreaming.value = false
        isLoading.value = false

        // If this was a new conversation, reload to get the ID
        if (!currentConversationId.value) {
          await loadConversations()
          if (conversations.value.length > 0) {
            currentConversationId.value = conversations.value[0].id
          }
        }
      },
      // On error
      (error) => {
        isStreaming.value = false
        isLoading.value = false
        messages.value.pop() // Remove failed assistant message
        uiStore.notifyError(error.message || 'Failed to send message')
      }
    )
  } catch (error) {
    isStreaming.value = false
    isLoading.value = false
    messages.value.pop()
    uiStore.notifyError(error.message || 'Failed to send message')
  }
}

async function generateCardsFromChat() {
  if (!currentConversationId.value) {
    uiStore.notifyWarning('Start a conversation first')
    return
  }

  if (!selectedDeckId.value) {
    uiStore.notifyWarning('Please select a deck first')
    return
  }

  try {
    const result = await chatApi.generateCardsFromChat(currentConversationId.value, {
      deckId: selectedDeckId.value,
      numCards: 10
    })
    uiStore.notifySuccess(`Generated ${result.cards?.length || 0} cards!`)
  } catch (error) {
    uiStore.notifyError('Failed to generate cards from chat')
  }
}
</script>

<template>
  <div class="container mx-auto max-w-6xl h-[calc(100vh-12rem)]">
    <div class="flex h-full gap-4">
      <!-- Sidebar - Conversations -->
      <div
        class="w-64 flex-shrink-0 bg-base-100 rounded-box shadow overflow-hidden flex flex-col"
        :class="{ 'hidden lg:flex': !showConversationList }"
      >
        <div class="p-4 border-b border-base-200">
          <Button @click="startNewConversation" variant="primary" class="w-full">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
            New Chat
          </Button>
        </div>

        <div class="flex-1 overflow-y-auto scrollbar-thin">
          <div v-if="conversations.length === 0" class="p-4 text-center text-base-content/60">
            No conversations yet
          </div>

          <div
            v-for="conv in conversations"
            :key="conv.id"
            class="p-3 hover:bg-base-200 cursor-pointer border-b border-base-200 group"
            :class="{ 'bg-base-200': currentConversationId === conv.id }"
            @click="loadConversation(conv.id)"
          >
            <div class="flex justify-between items-start">
              <div class="flex-1 min-w-0">
                <p class="font-medium truncate">{{ conv.title || 'New Chat' }}</p>
                <p class="text-sm text-base-content/60">
                  {{ new Date(conv.updatedAt).toLocaleDateString() }}
                </p>
              </div>
              <button
                class="btn btn-ghost btn-xs opacity-0 group-hover:opacity-100"
                @click.stop="deleteConversation(conv.id)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Main chat area -->
      <div class="flex-1 flex flex-col bg-base-100 rounded-box shadow overflow-hidden">
        <!-- Chat header -->
        <div class="p-4 border-b border-base-200 flex items-center justify-between">
          <div class="flex items-center gap-4">
            <button
              class="btn btn-ghost btn-sm lg:hidden"
              @click="showConversationList = !showConversationList"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <h2 class="font-semibold">
              {{ currentConversation?.title || 'New Chat' }}
            </h2>
          </div>

          <div class="flex items-center gap-2">
            <select
              v-model="selectedDeckId"
              class="select select-bordered select-sm"
            >
              <option :value="null">No deck selected</option>
              <option v-for="deck in decksStore.decks" :key="deck.id" :value="deck.id">
                {{ deck.name }}
              </option>
            </select>

            <Button
              @click="generateCardsFromChat"
              variant="secondary"
              size="sm"
              :disabled="!currentConversationId || !selectedDeckId"
            >
              Generate Cards
            </Button>
          </div>
        </div>

        <!-- Messages -->
        <ChatWindow
          :messages="messages"
          :isLoading="isLoading"
          :isStreaming="isStreaming"
          class="flex-1"
        />

        <!-- Input -->
        <ChatInput
          @send="sendMessage"
          :disabled="isLoading"
          :placeholder="selectedDeckId ? 'Ask about your cards or learning goals...' : 'Start a conversation...'"
        />
      </div>
    </div>
  </div>
</template>
