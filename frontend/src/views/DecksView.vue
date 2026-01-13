<script setup>
import { ref, onMounted, computed } from 'vue'
import { useDecksStore } from '@/stores/decks'
import { useUiStore } from '@/stores/ui'
import DeckList from '@/components/Decks/DeckList.vue'
import DeckForm from '@/components/Decks/DeckForm.vue'
import Button from '@/components/Common/Button.vue'
import Modal from '@/components/Common/Modal.vue'
import LoadingSpinner from '@/components/Common/LoadingSpinner.vue'

const decksStore = useDecksStore()
const uiStore = useUiStore()

const searchQuery = ref('')
const showCreateModal = ref(false)
const showEditModal = ref(false)
const editingDeck = ref(null)

const filteredDecks = computed(() => {
  if (!searchQuery.value) return decksStore.sortedDecks

  const query = searchQuery.value.toLowerCase()
  return decksStore.sortedDecks.filter(deck =>
    deck.name.toLowerCase().includes(query) ||
    deck.description?.toLowerCase().includes(query)
  )
})

onMounted(async () => {
  await decksStore.fetchDecks()
})

function openCreateModal() {
  showCreateModal.value = true
}

function openEditModal(deck) {
  editingDeck.value = deck
  showEditModal.value = true
}

async function handleCreate(deckData) {
  const deck = await decksStore.createDeck(deckData)
  if (deck) {
    showCreateModal.value = false
    uiStore.notifySuccess('Колода создана!')
  }
}

async function handleUpdate(deckData) {
  if (!editingDeck.value) return

  const deck = await decksStore.updateDeck(editingDeck.value.id, deckData)
  if (deck) {
    showEditModal.value = false
    editingDeck.value = null
    uiStore.notifySuccess('Колода обновлена!')
  }
}

async function handleDelete(deck) {
  if (!confirm(`Вы уверены, что хотите удалить "${deck.name}"? Это действие нельзя отменить.`)) {
    return
  }

  const success = await decksStore.deleteDeck(deck.id)
  if (success) {
    uiStore.notifySuccess('Колода удалена!')
  }
}
</script>

<template>
  <div class="container mx-auto max-w-7xl">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
      <div>
        <h1 class="text-3xl font-bold text-base-content">Мои колоды</h1>
        <p class="text-base-content/60 mt-1">
          {{ decksStore.deckCount }} колод, {{ decksStore.totalCards }} карточек
        </p>
      </div>

      <Button @click="openCreateModal" variant="primary">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        Новая колода
      </Button>
    </div>

    <!-- Search -->
    <div class="mb-6">
      <div class="form-control">
        <div class="input-group">
          <span class="bg-base-200">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-base-content/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </span>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Поиск колод..."
            class="input input-bordered w-full max-w-md"
          />
        </div>
      </div>
    </div>

    <!-- Loading state -->
    <LoadingSpinner v-if="decksStore.loading && !decksStore.decks.length" class="py-12" />

    <!-- Empty state -->
    <div v-else-if="!decksStore.decks.length" class="text-center py-16">
      <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-base-200 mb-4">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-base-content/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
      </div>
      <h2 class="text-xl font-semibold mb-2">Пока нет колод</h2>
      <p class="text-base-content/60 mb-4">Создайте первую колоду для начала обучения</p>
      <Button @click="openCreateModal" variant="primary">Создать первую колоду</Button>
    </div>

    <!-- No search results -->
    <div v-else-if="filteredDecks.length === 0" class="text-center py-12">
      <p class="text-base-content/60">Колоды не найдены</p>
    </div>

    <!-- Deck list -->
    <DeckList
      v-else
      :decks="filteredDecks"
      @edit="openEditModal"
      @delete="handleDelete"
    />

    <!-- Create Modal -->
    <Modal v-model="showCreateModal" title="Создать колоду">
      <DeckForm
        @submit="handleCreate"
        @cancel="showCreateModal = false"
        :loading="decksStore.loading"
      />
    </Modal>

    <!-- Edit Modal -->
    <Modal v-model="showEditModal" title="Редактировать колоду">
      <DeckForm
        v-if="editingDeck"
        :deck="editingDeck"
        @submit="handleUpdate"
        @cancel="showEditModal = false"
        :loading="decksStore.loading"
      />
    </Modal>
  </div>
</template>
