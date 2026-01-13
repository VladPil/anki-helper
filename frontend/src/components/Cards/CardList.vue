<script setup>
import { ref, computed } from 'vue'
import { useCardsStore } from '@/stores/cards'
import CardItem from './CardItem.vue'

const props = defineProps({
  cards: {
    type: Array,
    required: true
  },
  selectable: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['edit', 'delete', 'select'])

const cardsStore = useCardsStore()

const searchQuery = ref('')
const sortBy = ref('createdAt')
const sortOrder = ref('desc')

const filteredCards = computed(() => {
  let result = [...props.cards]

  // Filter by search query
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(card =>
      card.front.toLowerCase().includes(query) ||
      card.back.toLowerCase().includes(query)
    )
  }

  // Sort
  result.sort((a, b) => {
    let aVal = a[sortBy.value]
    let bVal = b[sortBy.value]

    if (sortBy.value === 'createdAt' || sortBy.value === 'updatedAt') {
      aVal = new Date(aVal).getTime()
      bVal = new Date(bVal).getTime()
    }

    if (sortOrder.value === 'asc') {
      return aVal > bVal ? 1 : -1
    } else {
      return aVal < bVal ? 1 : -1
    }
  })

  return result
})

const allSelected = computed(() =>
  props.cards.length > 0 && props.cards.every(c => cardsStore.selectedCards.includes(c.id))
)

function toggleSelectAll() {
  if (allSelected.value) {
    cardsStore.clearSelection()
  } else {
    cardsStore.selectAllCards()
  }
}
</script>

<template>
  <div>
    <!-- Toolbar -->
    <div class="flex flex-col sm:flex-row gap-4 mb-4">
      <div class="flex-1">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search cards..."
          class="input input-bordered w-full"
        />
      </div>
      <div class="flex gap-2">
        <select v-model="sortBy" class="select select-bordered">
          <option value="createdAt">Created Date</option>
          <option value="updatedAt">Updated Date</option>
          <option value="front">Front</option>
        </select>
        <button
          @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'"
          class="btn btn-ghost btn-square"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5 transition-transform"
            :class="{ 'rotate-180': sortOrder === 'asc' }"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Select all checkbox -->
    <div v-if="selectable && filteredCards.length > 0" class="mb-4">
      <label class="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          :checked="allSelected"
          @change="toggleSelectAll"
          class="checkbox checkbox-primary"
        />
        <span class="text-sm text-base-content/70">
          Select all ({{ cardsStore.selectedCount }} selected)
        </span>
      </label>
    </div>

    <!-- Cards grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <CardItem
        v-for="card in filteredCards"
        :key="card.id"
        :card="card"
        :selectable="selectable"
        :selected="cardsStore.selectedCards.includes(card.id)"
        @edit="emit('edit', card)"
        @delete="emit('delete', card)"
        @toggle-select="cardsStore.toggleCardSelection(card.id)"
      />
    </div>

    <!-- Empty state -->
    <div v-if="filteredCards.length === 0" class="text-center py-8">
      <p class="text-base-content/60">
        {{ searchQuery ? 'No cards match your search' : 'No cards yet' }}
      </p>
    </div>
  </div>
</template>
