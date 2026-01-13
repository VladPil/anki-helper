<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import Button from '@/components/Common/Button.vue'
import Alert from '@/components/Common/Alert.vue'

const router = useRouter()
const authStore = useAuthStore()
const uiStore = useUiStore()

const form = ref({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

const showPassword = ref(false)
const agreedToTerms = ref(false)

const passwordMatch = computed(() => {
  return form.value.password === form.value.confirmPassword
})

const passwordStrength = computed(() => {
  const password = form.value.password
  if (!password) return { score: 0, label: '', color: '' }

  let score = 0
  if (password.length >= 8) score++
  if (password.length >= 12) score++
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++
  if (/\d/.test(password)) score++
  if (/[^a-zA-Z0-9]/.test(password)) score++

  const levels = [
    { score: 0, label: '', color: '' },
    { score: 1, label: 'Слабый', color: 'bg-error' },
    { score: 2, label: 'Средний', color: 'bg-warning' },
    { score: 3, label: 'Хороший', color: 'bg-info' },
    { score: 4, label: 'Надёжный', color: 'bg-success' },
    { score: 5, label: 'Очень надёжный', color: 'bg-success' }
  ]

  return levels[score]
})

const isValid = computed(() => {
  return (
    form.value.email &&
    form.value.password.length >= 8 &&
    passwordMatch.value &&
    agreedToTerms.value
  )
})

async function handleSubmit() {
  if (!isValid.value) return

  const success = await authStore.register({
    username: form.value.username || undefined,
    email: form.value.email,
    password: form.value.password
  })

  if (success) {
    uiStore.notifySuccess('Аккаунт успешно создан!')
    router.push('/')
  }
}
</script>

<template>
  <div class="card w-full max-w-md bg-base-100 shadow-xl">
    <div class="card-body">
      <div class="text-center mb-6">
        <h1 class="text-3xl font-bold text-primary">AnkiRAG</h1>
        <p class="text-base-content/60 mt-2">Создайте аккаунт</p>
      </div>

      <Alert
        v-if="authStore.error"
        type="error"
        :message="authStore.error"
        :dismissible="true"
        @dismiss="authStore.clearError"
        class="mb-4"
      />

      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div class="form-control">
          <label class="label">
            <span class="label-text">Имя пользователя (необязательно)</span>
          </label>
          <input
            v-model="form.username"
            type="text"
            placeholder="Выберите имя"
            class="input input-bordered w-full"
            autocomplete="username"
          />
        </div>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Email</span>
          </label>
          <input
            v-model="form.email"
            type="email"
            placeholder="ваш@email.com"
            class="input input-bordered w-full"
            required
            autocomplete="email"
          />
        </div>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Пароль</span>
          </label>
          <div class="relative">
            <input
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="Придумайте пароль"
              class="input input-bordered w-full pr-10"
              required
              minlength="8"
              autocomplete="new-password"
            />
            <button
              type="button"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-base-content/50 hover:text-base-content"
              @click="showPassword = !showPassword"
            >
              <svg v-if="showPassword" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
              </svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
            </button>
          </div>
          <!-- Password strength indicator -->
          <div v-if="form.password" class="mt-2">
            <div class="flex gap-1 h-1">
              <div
                v-for="i in 5"
                :key="i"
                class="flex-1 rounded-full transition-colors"
                :class="i <= passwordStrength.score ? passwordStrength.color : 'bg-base-300'"
              ></div>
            </div>
            <p class="text-xs mt-1" :class="passwordStrength.score >= 3 ? 'text-success' : 'text-warning'">
              {{ passwordStrength.label }}
            </p>
          </div>
        </div>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Подтвердите пароль</span>
          </label>
          <input
            v-model="form.confirmPassword"
            :type="showPassword ? 'text' : 'password'"
            placeholder="Повторите пароль"
            class="input input-bordered w-full"
            :class="{ 'input-error': form.confirmPassword && !passwordMatch }"
            required
            autocomplete="new-password"
          />
          <label v-if="form.confirmPassword && !passwordMatch" class="label">
            <span class="label-text-alt text-error">Пароли не совпадают</span>
          </label>
        </div>

        <div class="form-control">
          <label class="label cursor-pointer justify-start gap-2">
            <input
              v-model="agreedToTerms"
              type="checkbox"
              class="checkbox checkbox-primary checkbox-sm"
              required
            />
            <span class="label-text">
              Я принимаю
              <a href="#" class="link link-primary">Условия использования</a>
              и
              <a href="#" class="link link-primary">Политику конфиденциальности</a>
            </span>
          </label>
        </div>

        <Button
          type="submit"
          variant="primary"
          class="w-full"
          :loading="authStore.loading"
          :disabled="!isValid"
        >
          Создать аккаунт
        </Button>
      </form>

      <div class="divider">ИЛИ</div>

      <p class="text-center text-base-content/60">
        Уже есть аккаунт?
        <router-link to="/login" class="link link-primary">Войти</router-link>
      </p>
    </div>
  </div>
</template>
