<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useDecksStore } from '@/stores/decks'
import { useCardsStore } from '@/stores/cards'
import { useUiStore } from '@/stores/ui'
import GenerationForm from '@/components/Generation/GenerationForm.vue'
import GenerationProgress from '@/components/Generation/GenerationProgress.vue'
import GenerationResult from '@/components/Generation/GenerationResult.vue'
import { generationApi } from '@/api/generation'

const route = useRoute()
const decksStore = useDecksStore()
const cardsStore = useCardsStore()
const uiStore = useUiStore()

const step = ref('form') // form, generating, result
const generatedCards = ref([])
const progress = ref({
  status: 'idle',
  message: '',
  progress: 0
})
const generationError = ref(null)

const selectedDeckId = computed(() => route.query.deckId || null)

onMounted(async () => {
  await decksStore.fetchDecks()
})

async function handleGenerate(params) {
  step.value = 'generating'
  progress.value = {
    status: 'processing',
    message: 'Анализ контента...',
    progress: 10
  }
  generationError.value = null

  try {
    // Simulate progress updates
    const progressUpdates = [
      { message: 'Извлечение ключевых концепций...', progress: 30 },
      { message: 'Генерация флеш-карточек...', progress: 60 },
      { message: 'Форматирование карточек...', progress: 80 },
      { message: 'Завершение...', progress: 95 }
    ]

    let updateIndex = 0
    const progressInterval = setInterval(() => {
      if (updateIndex < progressUpdates.length) {
        progress.value = {
          status: 'processing',
          ...progressUpdates[updateIndex]
        }
        updateIndex++
      }
    }, 1500)

    // Call appropriate API based on source type
    let result
    switch (params.sourceType) {
      case 'text':
        result = await generationApi.fromText(params)
        break
      case 'file':
        result = await generationApi.fromFile(params.file, params)
        break
      case 'url':
        result = await generationApi.fromUrl(params)
        break
      case 'topic':
        result = await generationApi.fromTopic(params)
        break
      default:
        result = await generationApi.fromText(params)
    }

    clearInterval(progressInterval)

    generatedCards.value = result.cards || result
    progress.value = {
      status: 'complete',
      message: 'Генерация завершена!',
      progress: 100
    }

    step.value = 'result'
  } catch (error) {
    generationError.value = error.message || 'Ошибка генерации'
    progress.value = {
      status: 'error',
      message: error.message || 'Ошибка генерации',
      progress: 0
    }
    step.value = 'form'
    uiStore.notifyError(error.message || 'Не удалось сгенерировать карточки')
  }
}

async function handleSaveCards(selectedCards, deckId) {
  if (!selectedCards.length || !deckId) return

  const cardsToSave = selectedCards.map(card => ({
    ...card,
    deckId
  }))

  const saved = await cardsStore.createCards(cardsToSave)
  if (saved) {
    uiStore.notifySuccess(`${saved.length} карточек сохранено в колоду!`)
    step.value = 'form'
    generatedCards.value = []
  }
}

function handleCancel() {
  step.value = 'form'
  generatedCards.value = []
  progress.value = {
    status: 'idle',
    message: '',
    progress: 0
  }
}

function startOver() {
  step.value = 'form'
  generatedCards.value = []
  generationError.value = null
}
</script>

<template>
  <div class="container mx-auto max-w-4xl">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-base-content">Генерация карточек</h1>
      <p class="text-base-content/60 mt-2">
        Используйте ИИ для автоматического создания флеш-карточек из вашего контента
      </p>
    </div>

    <!-- Step indicator -->
    <ul class="steps steps-horizontal w-full mb-8">
      <li class="step" :class="{ 'step-primary': step === 'form' || step === 'generating' || step === 'result' }">
        Настройка
      </li>
      <li class="step" :class="{ 'step-primary': step === 'generating' || step === 'result' }">
        Генерация
      </li>
      <li class="step" :class="{ 'step-primary': step === 'result' }">
        Проверка и сохранение
      </li>
    </ul>

    <!-- Form step -->
    <div v-if="step === 'form'">
      <GenerationForm
        :decks="decksStore.decks"
        :initialDeckId="selectedDeckId"
        :error="generationError"
        @generate="handleGenerate"
      />
    </div>

    <!-- Generating step -->
    <div v-else-if="step === 'generating'">
      <GenerationProgress
        :status="progress.status"
        :message="progress.message"
        :progress="progress.progress"
        @cancel="handleCancel"
      />
    </div>

    <!-- Result step -->
    <div v-else-if="step === 'result'">
      <GenerationResult
        :cards="generatedCards"
        :decks="decksStore.decks"
        :initialDeckId="selectedDeckId"
        @save="handleSaveCards"
        @regenerate="startOver"
        @cancel="startOver"
      />
    </div>
  </div>
</template>
