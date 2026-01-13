<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import Button from '@/components/Common/Button.vue'
import Alert from '@/components/Common/Alert.vue'

const authStore = useAuthStore()
const uiStore = useUiStore()

const activeTab = ref('profile')
const tokenCopied = ref(false)
const apiUrl = `${window.location.protocol}//${window.location.hostname}:8000`

// Profile form
const profileForm = ref({
  username: '',
  email: ''
})

// Password form
const passwordForm = ref({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

// Preferences
const preferences = ref({
  theme: 'light',
  cardsPerSession: 20,
  showTimer: true,
  autoPlayAudio: false,
  language: 'en'
})

const passwordMatch = computed(() =>
  passwordForm.value.newPassword === passwordForm.value.confirmPassword
)

onMounted(() => {
  if (authStore.user) {
    profileForm.value = {
      username: authStore.user.username || '',
      email: authStore.user.email || ''
    }
  }
  preferences.value.theme = uiStore.theme
})

async function updateProfile() {
  const success = await authStore.updateProfile(profileForm.value)
  if (success) {
    uiStore.notifySuccess('Профиль обновлён!')
  }
}

async function changePassword() {
  if (!passwordMatch.value) {
    uiStore.notifyError('Пароли не совпадают')
    return
  }

  const success = await authStore.changePassword({
    currentPassword: passwordForm.value.currentPassword,
    newPassword: passwordForm.value.newPassword
  })

  if (success) {
    uiStore.notifySuccess('Пароль успешно изменён!')
    passwordForm.value = {
      currentPassword: '',
      newPassword: '',
      confirmPassword: ''
    }
  }
}

function savePreferences() {
  uiStore.setTheme(preferences.value.theme)
  // Save other preferences to localStorage or API
  localStorage.setItem('preferences', JSON.stringify(preferences.value))
  uiStore.notifySuccess('Настройки сохранены!')
}

async function handleLogout() {
  await authStore.logout()
}

async function copyToken() {
  if (authStore.token) {
    await navigator.clipboard.writeText(authStore.token)
    tokenCopied.value = true
    uiStore.notifySuccess('Токен скопирован!')
    setTimeout(() => {
      tokenCopied.value = false
    }, 3000)
  }
}

async function copyApiUrl() {
  await navigator.clipboard.writeText(apiUrl)
  uiStore.notifySuccess('URL скопирован!')
}
</script>

<template>
  <div class="container mx-auto max-w-4xl">
    <h1 class="text-3xl font-bold text-base-content mb-8">Настройки</h1>

    <!-- Tabs -->
    <div class="tabs tabs-boxed mb-6">
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'profile' }"
        @click="activeTab = 'profile'"
      >
        Профиль
      </a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'security' }"
        @click="activeTab = 'security'"
      >
        Безопасность
      </a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'preferences' }"
        @click="activeTab = 'preferences'"
      >
        Предпочтения
      </a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'agent' }"
        @click="activeTab = 'agent'"
      >
        Anki-агент
      </a>
    </div>

    <!-- Profile Tab -->
    <div v-if="activeTab === 'profile'" class="card bg-base-100 shadow">
      <div class="card-body">
        <h2 class="card-title mb-4">Информация профиля</h2>

        <Alert
          v-if="authStore.error"
          type="error"
          :message="authStore.error"
          :dismissible="true"
          @dismiss="authStore.clearError"
          class="mb-4"
        />

        <form @submit.prevent="updateProfile" class="space-y-4">
          <div class="form-control">
            <label class="label">
              <span class="label-text">Имя пользователя</span>
            </label>
            <input
              v-model="profileForm.username"
              type="text"
              class="input input-bordered w-full max-w-md"
              placeholder="Ваше имя"
            />
          </div>

          <div class="form-control">
            <label class="label">
              <span class="label-text">Email</span>
            </label>
            <input
              v-model="profileForm.email"
              type="email"
              class="input input-bordered w-full max-w-md"
              placeholder="ваш@email.com"
            />
          </div>

          <div class="pt-4">
            <Button type="submit" variant="primary" :loading="authStore.loading">
              Сохранить
            </Button>
          </div>
        </form>
      </div>
    </div>

    <!-- Security Tab -->
    <div v-if="activeTab === 'security'" class="space-y-6">
      <div class="card bg-base-100 shadow">
        <div class="card-body">
          <h2 class="card-title mb-4">Смена пароля</h2>

          <Alert
            v-if="authStore.error"
            type="error"
            :message="authStore.error"
            :dismissible="true"
            @dismiss="authStore.clearError"
            class="mb-4"
          />

          <form @submit.prevent="changePassword" class="space-y-4">
            <div class="form-control">
              <label class="label">
                <span class="label-text">Текущий пароль</span>
              </label>
              <input
                v-model="passwordForm.currentPassword"
                type="password"
                class="input input-bordered w-full max-w-md"
                placeholder="Введите текущий пароль"
                required
              />
            </div>

            <div class="form-control">
              <label class="label">
                <span class="label-text">Новый пароль</span>
              </label>
              <input
                v-model="passwordForm.newPassword"
                type="password"
                class="input input-bordered w-full max-w-md"
                placeholder="Введите новый пароль"
                minlength="8"
                required
              />
            </div>

            <div class="form-control">
              <label class="label">
                <span class="label-text">Подтвердите новый пароль</span>
              </label>
              <input
                v-model="passwordForm.confirmPassword"
                type="password"
                class="input input-bordered w-full max-w-md"
                :class="{ 'input-error': passwordForm.confirmPassword && !passwordMatch }"
                placeholder="Повторите новый пароль"
                required
              />
              <label v-if="passwordForm.confirmPassword && !passwordMatch" class="label">
                <span class="label-text-alt text-error">Пароли не совпадают</span>
              </label>
            </div>

            <div class="pt-4">
              <Button
                type="submit"
                variant="primary"
                :loading="authStore.loading"
                :disabled="!passwordMatch"
              >
                Изменить пароль
              </Button>
            </div>
          </form>
        </div>
      </div>

      <div class="card bg-base-100 shadow">
        <div class="card-body">
          <h2 class="card-title text-error mb-4">Опасная зона</h2>
          <p class="text-base-content/60 mb-4">
            После выхода вам потребуется снова войти в аккаунт.
          </p>
          <Button @click="handleLogout" variant="error">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Выйти
          </Button>
        </div>
      </div>
    </div>

    <!-- Preferences Tab -->
    <div v-if="activeTab === 'preferences'" class="card bg-base-100 shadow">
      <div class="card-body">
        <h2 class="card-title mb-4">Предпочтения</h2>

        <form @submit.prevent="savePreferences" class="space-y-6">
          <!-- Theme -->
          <div class="form-control">
            <label class="label">
              <span class="label-text">Тема</span>
            </label>
            <div class="flex gap-4">
              <label class="label cursor-pointer gap-2">
                <input
                  v-model="preferences.theme"
                  type="radio"
                  value="light"
                  class="radio radio-primary"
                />
                <span class="label-text">Светлая</span>
              </label>
              <label class="label cursor-pointer gap-2">
                <input
                  v-model="preferences.theme"
                  type="radio"
                  value="dark"
                  class="radio radio-primary"
                />
                <span class="label-text">Тёмная</span>
              </label>
            </div>
          </div>

          <!-- Cards per session -->
          <div class="form-control">
            <label class="label">
              <span class="label-text">Карточек за сессию повторения</span>
            </label>
            <input
              v-model.number="preferences.cardsPerSession"
              type="range"
              min="5"
              max="100"
              step="5"
              class="range range-primary w-full max-w-md"
            />
            <div class="flex justify-between text-xs text-base-content/60 w-full max-w-md mt-1">
              <span>5</span>
              <span>{{ preferences.cardsPerSession }}</span>
              <span>100</span>
            </div>
          </div>

          <!-- Show timer -->
          <div class="form-control">
            <label class="label cursor-pointer justify-start gap-4">
              <input
                v-model="preferences.showTimer"
                type="checkbox"
                class="toggle toggle-primary"
              />
              <span class="label-text">Показывать таймер при повторении</span>
            </label>
          </div>

          <!-- Auto-play audio -->
          <div class="form-control">
            <label class="label cursor-pointer justify-start gap-4">
              <input
                v-model="preferences.autoPlayAudio"
                type="checkbox"
                class="toggle toggle-primary"
              />
              <span class="label-text">Автовоспроизведение аудио</span>
            </label>
          </div>

          <div class="pt-4">
            <Button type="submit" variant="primary">Сохранить</Button>
          </div>
        </form>
      </div>
    </div>

    <!-- Agent Tab -->
    <div v-if="activeTab === 'agent'" class="space-y-6">
      <div class="card bg-base-100 shadow">
        <div class="card-body">
          <h2 class="card-title mb-4">Настройка локального Anki-агента</h2>
          <p class="text-base-content/70 mb-6">
            Используйте эти данные для настройки локального агента синхронизации с Anki.
            Агент синхронизирует одобренные карточки из AnkiRAG в вашу локальную установку Anki.
          </p>

          <!-- API URL -->
          <div class="form-control mb-4">
            <label class="label">
              <span class="label-text font-medium">URL API</span>
            </label>
            <div class="join w-full max-w-lg">
              <input
                type="text"
                :value="apiUrl"
                readonly
                class="input input-bordered join-item flex-1 font-mono text-sm"
              />
              <Button @click="copyApiUrl" variant="secondary" class="join-item">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                Копировать
              </Button>
            </div>
          </div>

          <!-- Access Token -->
          <div class="form-control mb-6">
            <label class="label">
              <span class="label-text font-medium">Токен доступа</span>
            </label>
            <div class="join w-full max-w-lg">
              <input
                type="password"
                :value="authStore.token"
                readonly
                class="input input-bordered join-item flex-1 font-mono text-sm"
              />
              <Button @click="copyToken" :variant="tokenCopied ? 'success' : 'secondary'" class="join-item">
                <svg v-if="!tokenCopied" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
                {{ tokenCopied ? 'Скопировано!' : 'Копировать' }}
              </Button>
            </div>
            <label class="label">
              <span class="label-text-alt text-warning">
                Храните токен в безопасности. Он даёт полный доступ к вашему аккаунту.
              </span>
            </label>
          </div>

          <div class="divider"></div>

          <!-- Instructions -->
          <div class="prose prose-sm max-w-none">
            <h3 class="text-lg font-semibold mb-2">Инструкция по настройке</h3>
            <ol class="list-decimal list-inside space-y-2 text-base-content/80">
              <li>Скачайте и установите локальный агент AnkiRAG</li>
              <li>Запустите приложение агента</li>
              <li>Введите URL API и токен доступа, указанные выше</li>
              <li>Нажмите «Подключить» для начала синхронизации карточек</li>
            </ol>
          </div>
        </div>
      </div>

      <div class="alert alert-info">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 shrink-0 stroke-current" fill="none" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>
          Токен доступа действует 30 минут. Если агент потеряет соединение,
          вернитесь сюда, чтобы скопировать новый токен.
        </span>
      </div>
    </div>
  </div>
</template>
