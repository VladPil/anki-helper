<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDecksStore } from '@/stores/decks'
import { useCardsStore } from '@/stores/cards'
import { useUiStore } from '@/stores/ui'
import CardList from '@/components/Cards/CardList.vue'
import CardEditor from '@/components/Cards/CardEditor.vue'
import Button from '@/components/Common/Button.vue'
import Modal from '@/components/Common/Modal.vue'
import LoadingSpinner from '@/components/Common/LoadingSpinner.vue'

const props = defineProps({
  id: {
    type: String,
    required: true
  }
})

const route = useRoute()
const router = useRouter()
const decksStore = useDecksStore()
const cardsStore = useCardsStore()
const uiStore = useUiStore()

const loading = ref(true)
const showCardEditor = ref(false)
const editingCard = ref(null)
const activeTab = ref('cards')

const deck = computed(() => decksStore.currentDeck)
const cards = computed(() => cardsStore.cards)

async function loadDeck() {
  loading.value = true
  try {
    await decksStore.fetchDeck(props.id)
    await cardsStore.fetchCards({ deckId: props.id })
  } finally {
    loading.value = false
  }
}

onMounted(loadDeck)

watch(() => props.id, loadDeck)

function openCardEditor(card = null) {
  editingCard.value = card
  showCardEditor.value = true
}

async function handleSaveCard(cardData) {
  if (editingCard.value) {
    const updated = await cardsStore.updateCard(editingCard.value.id, cardData)
    if (updated) {
      uiStore.notifySuccess('Card updated successfully!')
      showCardEditor.value = false
      editingCard.value = null
    }
  } else {
    const created = await cardsStore.createCard({ ...cardData, deckId: props.id })
    if (created) {
      uiStore.notifySuccess('Card created successfully!')
      showCardEditor.value = false
    }
  }
}

async function handleDeleteCard(card) {
  if (!confirm('Are you sure you want to delete this card?')) return

  const success = await cardsStore.deleteCard(card.id)
  if (success) {
    uiStore.notifySuccess('Card deleted successfully!')
  }
}

async function handleDeleteSelected() {
  if (!cardsStore.hasSelectedCards) return

  if (!confirm(`Delete ${cardsStore.selectedCount} selected cards?`)) return

  const success = await cardsStore.deleteCards(cardsStore.selectedCards)
  if (success) {
    uiStore.notifySuccess(`${cardsStore.selectedCount} cards deleted!`)
  }
}

async function handleExport(format) {
  await decksStore.exportDeck(props.id, format)
  uiStore.notifySuccess('Deck exported successfully!')
}

function goToGenerate() {
  router.push({ name: 'generate', query: { deckId: props.id } })
}
</script>

<template>
  <div class="container mx-auto max-w-7xl">
    <LoadingSpinner v-if="loading" class="py-12" />

    <template v-else-if="deck">
      <!-- Header -->
      <div class="mb-6">
        <div class="flex items-center gap-2 text-sm text-base-content/60 mb-2">
          <router-link to="/decks" class="hover:text-primary">Decks</router-link>
          <span>/</span>
          <span>{{ deck.name }}</span>
        </div>

        <div class="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
          <div>
            <h1 class="text-3xl font-bold text-base-content">{{ deck.name }}</h1>
            <p v-if="deck.description" class="text-base-content/60 mt-1">
              {{ deck.description }}
            </p>
          </div>

          <div class="flex flex-wrap gap-2">
            <Button @click="openCardEditor()" variant="primary">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
              </svg>
              Add Card
            </Button>
            <Button @click="goToGenerate" variant="secondary">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Generate
            </Button>
            <div class="dropdown dropdown-end">
              <label tabindex="0" class="btn btn-ghost">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                </svg>
              </label>
              <ul tabindex="0" class="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-52">
                <li><a @click="handleExport('apkg')">Export as .apkg</a></li>
                <li><a @click="handleExport('csv')">Export as CSV</a></li>
                <li><a @click="handleExport('json')">Export as JSON</a></li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <!-- Stats -->
      <div class="stats stats-vertical sm:stats-horizontal shadow mb-6 w-full">
        <div class="stat">
          <div class="stat-title">Total Cards</div>
          <div class="stat-value text-primary">{{ cards.length }}</div>
        </div>
        <div class="stat">
          <div class="stat-title">Due Today</div>
          <div class="stat-value text-accent">{{ deck.dueCount || 0 }}</div>
        </div>
        <div class="stat">
          <div class="stat-title">New Cards</div>
          <div class="stat-value text-secondary">{{ deck.newCount || 0 }}</div>
        </div>
        <div class="stat">
          <div class="stat-title">Learning</div>
          <div class="stat-value text-info">{{ deck.learningCount || 0 }}</div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs tabs-boxed mb-4">
        <a
          class="tab"
          :class="{ 'tab-active': activeTab === 'cards' }"
          @click="activeTab = 'cards'"
        >
          Cards
        </a>
        <a
          class="tab"
          :class="{ 'tab-active': activeTab === 'stats' }"
          @click="activeTab = 'stats'"
        >
          Statistics
        </a>
      </div>

      <!-- Cards Tab -->
      <div v-if="activeTab === 'cards'">
        <!-- Bulk actions -->
        <div v-if="cardsStore.hasSelectedCards" class="flex items-center gap-4 mb-4 p-4 bg-base-200 rounded-lg">
          <span class="text-sm">{{ cardsStore.selectedCount }} selected</span>
          <Button @click="handleDeleteSelected" variant="error" size="sm">
            Delete Selected
          </Button>
          <Button @click="cardsStore.clearSelection" variant="ghost" size="sm">
            Clear Selection
          </Button>
        </div>

        <!-- Card list -->
        <CardList
          :cards="cards"
          :selectable="true"
          @edit="openCardEditor"
          @delete="handleDeleteCard"
        />

        <!-- Empty state -->
        <div v-if="cards.length === 0" class="text-center py-12">
          <p class="text-base-content/60 mb-4">No cards in this deck yet</p>
          <div class="flex justify-center gap-4">
            <Button @click="openCardEditor()" variant="primary">Add Card Manually</Button>
            <Button @click="goToGenerate" variant="secondary">Generate with AI</Button>
          </div>
        </div>
      </div>

      <!-- Stats Tab -->
      <div v-if="activeTab === 'stats'" class="card bg-base-100 shadow">
        <div class="card-body">
          <h3 class="card-title">Learning Statistics</h3>
          <p class="text-base-content/60">Statistics will be shown here once you start reviewing cards.</p>
        </div>
      </div>
    </template>

    <!-- Deck not found -->
    <div v-else class="text-center py-12">
      <h2 class="text-xl font-semibold mb-2">Deck not found</h2>
      <p class="text-base-content/60 mb-4">This deck may have been deleted or you don't have access to it.</p>
      <Button @click="router.push('/decks')" variant="primary">Go to Decks</Button>
    </div>

    <!-- Card Editor Modal -->
    <Modal
      v-model="showCardEditor"
      :title="editingCard ? 'Edit Card' : 'Add New Card'"
      size="lg"
    >
      <CardEditor
        :card="editingCard"
        @save="handleSaveCard"
        @cancel="showCardEditor = false"
        :loading="cardsStore.loading"
      />
    </Modal>
  </div>
</template>
