<script setup>
import { ref, watch, computed } from 'vue'
import Button from '@/components/Common/Button.vue'

const props = defineProps({
  card: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['save', 'cancel'])

const form = ref({
  front: '',
  back: '',
  tags: []
})

const tagInput = ref('')

// Initialize form with card data if editing
watch(() => props.card, (newCard) => {
  if (newCard) {
    form.value = {
      front: newCard.front || '',
      back: newCard.back || '',
      tags: [...(newCard.tags || [])]
    }
  } else {
    form.value = {
      front: '',
      back: '',
      tags: []
    }
  }
}, { immediate: true })

const isValid = computed(() => {
  return form.value.front.trim() && form.value.back.trim()
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
  emit('save', { ...form.value })
}
</script>

<template>
  <form @submit.prevent="handleSubmit" class="space-y-4">
    <!-- Front -->
    <div class="form-control">
      <label class="label">
        <span class="label-text font-medium">Front (Question)</span>
      </label>
      <textarea
        v-model="form.front"
        class="textarea textarea-bordered h-32 resize-none"
        placeholder="Enter the question or prompt..."
        required
      ></textarea>
    </div>

    <!-- Back -->
    <div class="form-control">
      <label class="label">
        <span class="label-text font-medium">Back (Answer)</span>
      </label>
      <textarea
        v-model="form.back"
        class="textarea textarea-bordered h-32 resize-none"
        placeholder="Enter the answer..."
        required
      ></textarea>
    </div>

    <!-- Tags -->
    <div class="form-control">
      <label class="label">
        <span class="label-text font-medium">Tags (optional)</span>
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
          placeholder="Add a tag..."
          @keydown="handleTagKeydown"
        />
        <button type="button" @click="addTag" class="btn btn-primary join-item">
          Add
        </button>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex justify-end gap-2 pt-4">
      <Button type="button" variant="ghost" @click="emit('cancel')">
        Cancel
      </Button>
      <Button type="submit" variant="primary" :loading="loading" :disabled="!isValid">
        {{ card ? 'Update Card' : 'Create Card' }}
      </Button>
    </div>
  </form>
</template>
