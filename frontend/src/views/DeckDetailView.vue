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
      uiStore.notifySuccess('Карточка обновлена!')
      showCardEditor.value = false
      editingCard.value = null
    }
  } else {
    const created = await cardsStore.createCard({ ...cardData, deckId: props.id })
    if (created) {
      uiStore.notifySuccess('Карточка создана!')
      showCardEditor.value = false
    }
  }
}

async function handleDeleteCard(card) {
  if (!confirm('Вы уверены, что хотите удалить эту карточку?')) return

  const success = await cardsStore.deleteCard(card.id)
  if (success) {
    uiStore.notifySuccess('Карточка удалена!')
  }
}

async function handleDeleteSelected() {
  if (!cardsStore.hasSelectedCards) return

  if (!confirm(`Удалить ${cardsStore.selectedCount} выбранных карточек?`)) return

  const success = await cardsStore.deleteCards(cardsStore.selectedCards)
  if (success) {
    uiStore.notifySuccess(`${cardsStore.selectedCount} карточек удалено!`)
  }
}

async function handleApproveCard(card) {
  const result = await cardsStore.approveCard(card.id)
  if (result) {
    uiStore.notifySuccess('Карточка одобрена для синхронизации!')
  }
}

async function handleRejectCard(card) {
  const reason = prompt('Укажите причину отклонения (необязательно):')
  if (reason === null) return // User cancelled

  const result = await cardsStore.rejectCard(card.id, reason || 'Отклонено пользователем')
  if (result) {
    uiStore.notifySuccess('Карточка отклонена')
  }
}

async function handleApproveSelected() {
  if (!cardsStore.hasSelectedCards) return

  const result = await cardsStore.approveCards(cardsStore.selectedCards)
  if (result) {
    uiStore.notifySuccess(`${result.total_created} карточек одобрено!`)
  }
}

async function handleExport(format) {
  await decksStore.exportDeck(props.id, format)
  uiStore.notifySuccess('Колода экспортирована!')
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
          <router-link to="/decks" class="hover:text-primary">Колоды</router-link>
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
              Добавить карточку
            </Button>
            <Button @click="goToGenerate" variant="secondary">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Генерировать
            </Button>
            <div class="dropdown dropdown-end">
              <label tabindex="0" class="btn btn-ghost">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                </svg>
              </label>
              <ul tabindex="0" class="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-52">
                <li><a @click="handleExport('apkg')">Экспорт в .apkg</a></li>
                <li><a @click="handleExport('csv')">Экспорт в CSV</a></li>
                <li><a @click="handleExport('json')">Экспорт в JSON</a></li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <!-- Stats -->
      <div class="stats stats-vertical sm:stats-horizontal shadow mb-6 w-full">
        <div class="stat">
          <div class="stat-title">Всего карточек</div>
          <div class="stat-value text-primary">{{ cards.length }}</div>
        </div>
        <div class="stat">
          <div class="stat-title">К повторению</div>
          <div class="stat-value text-accent">{{ deck.dueCount || 0 }}</div>
        </div>
        <div class="stat">
          <div class="stat-title">Новых</div>
          <div class="stat-value text-secondary">{{ deck.newCount || 0 }}</div>
        </div>
        <div class="stat">
          <div class="stat-title">Изучаемых</div>
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
          Карточки
        </a>
        <a
          class="tab"
          :class="{ 'tab-active': activeTab === 'stats' }"
          @click="activeTab = 'stats'"
        >
          Статистика
        </a>
      </div>

      <!-- Cards Tab -->
      <div v-if="activeTab === 'cards'">
        <!-- Bulk actions -->
        <div v-if="cardsStore.hasSelectedCards" class="flex flex-wrap items-center gap-4 mb-4 p-4 bg-base-200 rounded-lg">
          <span class="text-sm">{{ cardsStore.selectedCount }} выбрано</span>
          <Button @click="handleApproveSelected" variant="success" size="sm">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            Одобрить выбранные
          </Button>
          <Button @click="handleDeleteSelected" variant="error" size="sm">
            Удалить выбранные
          </Button>
          <Button @click="cardsStore.clearSelection" variant="ghost" size="sm">
            Сбросить выбор
          </Button>
        </div>

        <!-- Card list -->
        <CardList
          :cards="cards"
          :selectable="true"
          @edit="openCardEditor"
          @delete="handleDeleteCard"
          @approve="handleApproveCard"
          @reject="handleRejectCard"
        />

        <!-- Empty state -->
        <div v-if="cards.length === 0" class="text-center py-12">
          <p class="text-base-content/60 mb-4">В этой колоде пока нет карточек</p>
          <div class="flex justify-center gap-4">
            <Button @click="openCardEditor()" variant="primary">Добавить вручную</Button>
            <Button @click="goToGenerate" variant="secondary">Сгенерировать с ИИ</Button>
          </div>
        </div>
      </div>

      <!-- Stats Tab -->
      <div v-if="activeTab === 'stats'" class="card bg-base-100 shadow">
        <div class="card-body">
          <h3 class="card-title">Статистика обучения</h3>
          <p class="text-base-content/60">Статистика появится после начала повторения карточек.</p>
        </div>
      </div>
    </template>

    <!-- Deck not found -->
    <div v-else class="text-center py-12">
      <h2 class="text-xl font-semibold mb-2">Колода не найдена</h2>
      <p class="text-base-content/60 mb-4">Эта колода была удалена или у вас нет к ней доступа.</p>
      <Button @click="router.push('/decks')" variant="primary">К списку колод</Button>
    </div>

    <!-- Card Editor Modal -->
    <Modal
      v-model="showCardEditor"
      :title="editingCard ? 'Редактировать карточку' : 'Новая карточка'"
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
