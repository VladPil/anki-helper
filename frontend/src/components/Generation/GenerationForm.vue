<script setup>
import { ref, computed, watch } from 'vue'
import Button from '@/components/Common/Button.vue'
import Alert from '@/components/Common/Alert.vue'

const props = defineProps({
  decks: {
    type: Array,
    default: () => []
  },
  initialDeckId: {
    type: String,
    default: null
  },
  error: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['generate'])

const sourceType = ref('text')
const form = ref({
  content: '',
  url: '',
  topic: '',
  file: null,
  deckId: null,
  numCards: 10,
  difficulty: 'medium',
  cardType: 'basic',
  language: 'ru'
})

const fileName = ref('')

// Set initial deck ID
watch(() => props.initialDeckId, (id) => {
  if (id) form.value.deckId = id
}, { immediate: true })

const isValid = computed(() => {
  if (!form.value.deckId) return false

  switch (sourceType.value) {
    case 'text':
      return form.value.content.trim().length >= 50
    case 'url':
      return isValidUrl(form.value.url)
    case 'topic':
      return form.value.topic.trim().length >= 3
    case 'file':
      return form.value.file !== null
    default:
      return false
  }
})

function isValidUrl(url) {
  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}

function handleFileSelect(event) {
  const file = event.target.files[0]
  if (file) {
    form.value.file = file
    fileName.value = file.name
  }
}

function handleSubmit() {
  if (!isValid.value) return

  const params = {
    sourceType: sourceType.value,
    deckId: form.value.deckId,
    numCards: form.value.numCards,
    difficulty: form.value.difficulty,
    cardType: form.value.cardType,
    language: form.value.language
  }

  switch (sourceType.value) {
    case 'text':
      params.content = form.value.content
      break
    case 'url':
      params.url = form.value.url
      break
    case 'topic':
      params.topic = form.value.topic
      break
    case 'file':
      params.file = form.value.file
      break
  }

  emit('generate', params)
}
</script>

<template>
  <div class="card bg-base-100 shadow-lg">
    <div class="card-body">
      <Alert
        v-if="error"
        type="error"
        :message="error"
        class="mb-4"
      />

      <form @submit.prevent="handleSubmit" class="space-y-6">
        <!-- Source type tabs -->
        <div class="tabs tabs-boxed">
          <a
            class="tab"
            :class="{ 'tab-active': sourceType === 'text' }"
            @click="sourceType = 'text'"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Текст
          </a>
          <a
            class="tab"
            :class="{ 'tab-active': sourceType === 'file' }"
            @click="sourceType = 'file'"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            Файл
          </a>
          <a
            class="tab"
            :class="{ 'tab-active': sourceType === 'url' }"
            @click="sourceType = 'url'"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
            URL
          </a>
          <a
            class="tab"
            :class="{ 'tab-active': sourceType === 'topic' }"
            @click="sourceType = 'topic'"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            Тема
          </a>
        </div>

        <!-- Source input based on type -->
        <div class="form-control">
          <!-- Text input -->
          <div v-if="sourceType === 'text'">
            <label class="label">
              <span class="label-text font-medium">Вставьте текст</span>
              <span class="label-text-alt">Мин. 50 символов</span>
            </label>
            <textarea
              v-model="form.content"
              class="textarea textarea-bordered h-48 resize-none"
              placeholder="Вставьте ваши заметки, статью или любой текстовый контент..."
            ></textarea>
          </div>

          <!-- File input -->
          <div v-if="sourceType === 'file'">
            <label class="label">
              <span class="label-text font-medium">Загрузите документ</span>
              <span class="label-text-alt">PDF, DOCX, TXT, MD</span>
            </label>
            <div class="flex items-center gap-4">
              <input
                type="file"
                accept=".pdf,.docx,.doc,.txt,.md"
                class="file-input file-input-bordered w-full"
                @change="handleFileSelect"
              />
            </div>
            <p v-if="fileName" class="text-sm text-success mt-2">
              Выбрано: {{ fileName }}
            </p>
          </div>

          <!-- URL input -->
          <div v-if="sourceType === 'url'">
            <label class="label">
              <span class="label-text font-medium">Введите URL</span>
            </label>
            <input
              v-model="form.url"
              type="url"
              class="input input-bordered w-full"
              placeholder="https://example.com/article"
            />
          </div>

          <!-- Topic input -->
          <div v-if="sourceType === 'topic'">
            <label class="label">
              <span class="label-text font-medium">Введите тему</span>
            </label>
            <input
              v-model="form.topic"
              type="text"
              class="input input-bordered w-full"
              placeholder="например: Фотосинтез, Вторая мировая война, Машинное обучение"
            />
          </div>
        </div>

        <!-- Target deck -->
        <div class="form-control">
          <label class="label">
            <span class="label-text font-medium">Целевая колода *</span>
          </label>
          <select v-model="form.deckId" class="select select-bordered w-full" required>
            <option :value="null" disabled>Выберите колоду</option>
            <option v-for="deck in decks" :key="deck.id" :value="deck.id">
              {{ deck.name }}
            </option>
          </select>
        </div>

        <!-- Options -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Number of cards -->
          <div class="form-control">
            <label class="label">
              <span class="label-text font-medium">Количество карточек</span>
            </label>
            <input
              v-model.number="form.numCards"
              type="range"
              min="5"
              max="50"
              step="5"
              class="range range-primary"
            />
            <div class="flex justify-between text-xs text-base-content/60 mt-1">
              <span>5</span>
              <span class="font-medium">{{ form.numCards }}</span>
              <span>50</span>
            </div>
          </div>

          <!-- Difficulty -->
          <div class="form-control">
            <label class="label">
              <span class="label-text font-medium">Сложность</span>
            </label>
            <select v-model="form.difficulty" class="select select-bordered w-full">
              <option value="easy">Лёгкая</option>
              <option value="medium">Средняя</option>
              <option value="hard">Сложная</option>
            </select>
          </div>

          <!-- Card type -->
          <div class="form-control">
            <label class="label">
              <span class="label-text font-medium">Тип карточек</span>
            </label>
            <select v-model="form.cardType" class="select select-bordered w-full">
              <option value="basic">Базовый (Вопрос-Ответ)</option>
              <option value="cloze">С пропусками</option>
              <option value="reversed">Двусторонний</option>
            </select>
          </div>

          <!-- Language -->
          <div class="form-control">
            <label class="label">
              <span class="label-text font-medium">Язык</span>
            </label>
            <select v-model="form.language" class="select select-bordered w-full">
              <option value="ru">Русский</option>
              <option value="en">English</option>
              <option value="es">Español</option>
              <option value="fr">Français</option>
              <option value="de">Deutsch</option>
            </select>
          </div>
        </div>

        <!-- Submit -->
        <div class="flex justify-end pt-4">
          <Button type="submit" variant="primary" size="lg" :disabled="!isValid">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Генерировать карточки
          </Button>
        </div>
      </form>
    </div>
  </div>
</template>
