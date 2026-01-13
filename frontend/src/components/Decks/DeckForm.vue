<script setup>
import { ref, watch, computed } from 'vue'
import Button from '@/components/Common/Button.vue'

const props = defineProps({
  deck: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['submit', 'cancel'])

const form = ref({
  name: '',
  description: '',
  tags: []
})

const tagInput = ref('')

// Initialize form with deck data if editing
watch(() => props.deck, (newDeck) => {
  if (newDeck) {
    form.value = {
      name: newDeck.name || '',
      description: newDeck.description || '',
      tags: [...(newDeck.tags || [])]
    }
  } else {
    form.value = {
      name: '',
      description: '',
      tags: []
    }
  }
}, { immediate: true })

const isValid = computed(() => {
  return form.value.name.trim().length > 0
})

function addTag() {
  const tag = tagInput.value.trim()
  if (tag && !form.value.tags.includes(tag)) {
    form.value.tags.push(tag)
    tagInput.value = ''
  }
}

function removeTag(index) {
  form.value.tags.splice(index, 1)
}

function handleTagKeydown(e) {
  if (e.key === 'Enter') {
    e.preventDefault()
    addTag()
  }
}

function handleSubmit() {
  if (!isValid.value) return
  emit('submit', { ...form.value })
}
</script>

<template>
  <form @submit.prevent="handleSubmit" class="space-y-4">
    <!-- Name -->
    <div class="form-control">
      <label class="label">
        <span class="label-text font-medium">Название колоды *</span>
      </label>
      <input
        v-model="form.name"
        type="text"
        class="input input-bordered w-full"
        placeholder="Введите название..."
        required
        autofocus
      />
    </div>

    <!-- Description -->
    <div class="form-control">
      <label class="label">
        <span class="label-text font-medium">Описание</span>
      </label>
      <textarea
        v-model="form.description"
        class="textarea textarea-bordered h-24 resize-none"
        placeholder="Опишите, о чём эта колода..."
      ></textarea>
    </div>

    <!-- Tags -->
    <div class="form-control">
      <label class="label">
        <span class="label-text font-medium">Теги</span>
      </label>
      <div class="flex flex-wrap gap-2 mb-2">
        <span
          v-for="(tag, index) in form.tags"
          :key="tag"
          class="badge badge-primary gap-1"
        >
          {{ tag }}
          <button type="button" @click="removeTag(index)" class="btn btn-ghost btn-xs p-0">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </span>
      </div>
      <div class="join w-full">
        <input
          v-model="tagInput"
          type="text"
          class="input input-bordered join-item flex-1"
          placeholder="Добавить тег..."
          @keydown="handleTagKeydown"
        />
        <button type="button" @click="addTag" class="btn btn-ghost join-item">
          Добавить
        </button>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex justify-end gap-2 pt-4">
      <Button type="button" variant="ghost" @click="emit('cancel')">
        Отмена
      </Button>
      <Button type="submit" variant="primary" :loading="loading" :disabled="!isValid">
        {{ deck ? 'Сохранить' : 'Создать' }}
      </Button>
    </div>
  </form>
</template>
