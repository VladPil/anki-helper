<script setup>
import { ref, computed, watch } from 'vue'
import Button from '@/components/Common/Button.vue'
import CardPreview from '@/components/Cards/CardPreview.vue'

const props = defineProps({
  cards: {
    type: Array,
    required: true
  },
  decks: {
    type: Array,
    default: () => []
  },
  initialDeckId: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['save', 'regenerate', 'cancel'])

const selectedCards = ref([])
const targetDeckId = ref(null)
const editingIndex = ref(null)
const editForm = ref({ front: '', back: '' })

// Initialize selections
watch(() => props.cards, (newCards) => {
  selectedCards.value = newCards.map((_, i) => i)
}, { immediate: true })

watch(() => props.initialDeckId, (id) => {
  if (id) targetDeckId.value = id
}, { immediate: true })

const selectedCount = computed(() => selectedCards.value.length)
const allSelected = computed(() => selectedCards.value.length === props.cards.length)

function toggleCard(index) {
  const idx = selectedCards.value.indexOf(index)
  if (idx === -1) {
    selectedCards.value.push(index)
  } else {
    selectedCards.value.splice(idx, 1)
  }
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedCards.value = []
  } else {
    selectedCards.value = props.cards.map((_, i) => i)
  }
}

function startEdit(index) {
  editingIndex.value = index
  editForm.value = {
    front: props.cards[index].front,
    back: props.cards[index].back
  }
}

function saveEdit() {
  if (editingIndex.value !== null) {
    props.cards[editingIndex.value].front = editForm.value.front
    props.cards[editingIndex.value].back = editForm.value.back
    editingIndex.value = null
  }
}

function cancelEdit() {
  editingIndex.value = null
}

function removeCard(index) {
  selectedCards.value = selectedCards.value.filter(i => i !== index)
}

function handleSave() {
  if (!targetDeckId.value || selectedCount.value === 0) return

  const cardsToSave = selectedCards.value.map(i => props.cards[i])
  emit('save', cardsToSave, targetDeckId.value)
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="card bg-base-100 shadow">
      <div class="card-body">
        <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h2 class="text-xl font-bold">Generated Cards</h2>
            <p class="text-base-content/70">
              {{ cards.length }} cards generated. Select the ones you want to save.
            </p>
          </div>

          <div class="flex items-center gap-4">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                :checked="allSelected"
                @change="toggleSelectAll"
                class="checkbox checkbox-primary"
              />
              <span class="text-sm">Select all</span>
            </label>
            <span class="badge badge-primary">{{ selectedCount }} selected</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Cards grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="(card, index) in cards"
        :key="index"
        class="relative"
      >
        <!-- Selection checkbox -->
        <div class="absolute top-2 left-2 z-10">
          <input
            type="checkbox"
            :checked="selectedCards.includes(index)"
            @change="toggleCard(index)"
            class="checkbox checkbox-primary"
          />
        </div>

        <!-- Edit/Remove buttons -->
        <div class="absolute top-2 right-2 z-10 flex gap-1">
          <button
            @click="startEdit(index)"
            class="btn btn-ghost btn-xs btn-circle bg-base-100"
            title="Edit"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button
            @click="removeCard(index)"
            class="btn btn-ghost btn-xs btn-circle bg-base-100 text-error"
            title="Remove"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Card preview -->
        <div
          :class="{ 'opacity-50': !selectedCards.includes(index) }"
        >
          <CardPreview :card="card" />
        </div>
      </div>
    </div>

    <!-- Edit modal -->
    <div v-if="editingIndex !== null" class="modal modal-open">
      <div class="modal-box">
        <h3 class="font-bold text-lg mb-4">Edit Card</h3>

        <div class="form-control mb-4">
          <label class="label">
            <span class="label-text">Front</span>
          </label>
          <textarea
            v-model="editForm.front"
            class="textarea textarea-bordered h-24"
          ></textarea>
        </div>

        <div class="form-control mb-4">
          <label class="label">
            <span class="label-text">Back</span>
          </label>
          <textarea
            v-model="editForm.back"
            class="textarea textarea-bordered h-24"
          ></textarea>
        </div>

        <div class="modal-action">
          <Button @click="cancelEdit" variant="ghost">Cancel</Button>
          <Button @click="saveEdit" variant="primary">Save</Button>
        </div>
      </div>
    </div>

    <!-- Save section -->
    <div class="card bg-base-100 shadow sticky bottom-4">
      <div class="card-body">
        <div class="flex flex-col sm:flex-row justify-between items-center gap-4">
          <div class="flex items-center gap-4 w-full sm:w-auto">
            <label class="label-text font-medium">Save to:</label>
            <select
              v-model="targetDeckId"
              class="select select-bordered flex-1 sm:w-64"
            >
              <option :value="null" disabled>Select a deck</option>
              <option v-for="deck in decks" :key="deck.id" :value="deck.id">
                {{ deck.name }}
              </option>
            </select>
          </div>

          <div class="flex gap-2 w-full sm:w-auto">
            <Button @click="emit('cancel')" variant="ghost" class="flex-1 sm:flex-none">
              Cancel
            </Button>
            <Button @click="emit('regenerate')" variant="secondary" class="flex-1 sm:flex-none">
              Regenerate
            </Button>
            <Button
              @click="handleSave"
              variant="primary"
              :disabled="!targetDeckId || selectedCount === 0"
              class="flex-1 sm:flex-none"
            >
              Save {{ selectedCount }} Cards
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
