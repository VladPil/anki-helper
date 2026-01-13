<script setup>
import { useRouter } from 'vue-router'
import Button from '@/components/Common/Button.vue'

const router = useRouter()

function navigateTo(path) {
  router.push(path)
}
</script>

<template>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
    <div class="card bg-base-100 shadow-lg">
      <div class="card-body">
        <h2 class="card-title">Быстрые действия</h2>
        <div class="flex flex-wrap gap-3 mt-4">
          <Button @click="navigateTo('/generate')" variant="primary">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Генерация карточек
          </Button>
          <Button @click="navigateTo('/chat')" variant="secondary">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            ИИ-чат
          </Button>
          <Button @click="navigateTo('/decks')" variant="ghost">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Новая колода
          </Button>
        </div>
      </div>
    </div>

    <div class="card bg-gradient-to-br from-primary to-secondary text-primary-content shadow-lg">
      <div class="card-body">
        <h2 class="card-title">Начать обучение</h2>
        <p class="opacity-90">Повторяйте карточки и улучшайте запоминание материала.</p>
        <div class="card-actions justify-end mt-4">
          <Button variant="ghost" class="bg-white/20 hover:bg-white/30 border-none text-white">
            Начать повторение
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
