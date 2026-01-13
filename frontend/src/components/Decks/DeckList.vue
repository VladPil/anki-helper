<script setup>
import DeckItem from './DeckItem.vue'

defineProps({
  decks: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['edit', 'delete'])
</script>

<template>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    <DeckItem
      v-for="deck in decks"
      :key="deck.id"
      :deck="deck"
      @edit="emit('edit', deck)"
      @delete="emit('delete', deck)"
    />
  </div>
</template>
