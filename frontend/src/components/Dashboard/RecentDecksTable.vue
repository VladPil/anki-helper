<script setup>
import { useRouter } from 'vue-router'
import Button from '@/components/Common/Button.vue'

const router = useRouter()

defineProps({
  decks: {
    type: Array,
    required: true
  }
})

function navigateTo(path) {
  router.push(path)
}

function formatDate(dateString) {
  return new Date(dateString).toLocaleDateString()
}
</script>

<template>
  <div class="card bg-base-100 shadow-lg">
    <div class="card-body">
      <div class="flex justify-between items-center mb-4">
        <h2 class="card-title">Недавние колоды</h2>
        <Button @click="navigateTo('/decks')" variant="ghost" size="sm">
          Все колоды
        </Button>
      </div>

      <div v-if="decks.length === 0" class="text-center py-8 text-base-content/60">
        <p>Пока нет колод. Создайте первую колоду для начала!</p>
        <Button @click="navigateTo('/decks')" variant="primary" class="mt-4">
          Создать колоду
        </Button>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="table table-zebra">
          <thead>
            <tr>
              <th>Название</th>
              <th>Карточек</th>
              <th>К повторению</th>
              <th>Обновлено</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="deck in decks" :key="deck.id" class="hover cursor-pointer" @click="navigateTo(`/decks/${deck.id}`)">
              <td class="font-medium">{{ deck.name }}</td>
              <td>{{ deck.cardCount || 0 }}</td>
              <td>
                <span class="badge badge-accent badge-sm">{{ deck.dueCount || 0 }}</span>
              </td>
              <td class="text-base-content/60">
                {{ formatDate(deck.updatedAt) }}
              </td>
              <td>
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-base-content/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
