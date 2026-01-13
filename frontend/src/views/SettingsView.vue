<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import Button from '@/components/Common/Button.vue'
import Alert from '@/components/Common/Alert.vue'

const authStore = useAuthStore()
const uiStore = useUiStore()

const activeTab = ref('profile')

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
    uiStore.notifySuccess('Profile updated successfully!')
  }
}

async function changePassword() {
  if (!passwordMatch.value) {
    uiStore.notifyError('Passwords do not match')
    return
  }

  const success = await authStore.changePassword({
    currentPassword: passwordForm.value.currentPassword,
    newPassword: passwordForm.value.newPassword
  })

  if (success) {
    uiStore.notifySuccess('Password changed successfully!')
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
  uiStore.notifySuccess('Preferences saved!')
}

async function handleLogout() {
  await authStore.logout()
}
</script>

<template>
  <div class="container mx-auto max-w-4xl">
    <h1 class="text-3xl font-bold text-base-content mb-8">Settings</h1>

    <!-- Tabs -->
    <div class="tabs tabs-boxed mb-6">
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'profile' }"
        @click="activeTab = 'profile'"
      >
        Profile
      </a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'security' }"
        @click="activeTab = 'security'"
      >
        Security
      </a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'preferences' }"
        @click="activeTab = 'preferences'"
      >
        Preferences
      </a>
    </div>

    <!-- Profile Tab -->
    <div v-if="activeTab === 'profile'" class="card bg-base-100 shadow">
      <div class="card-body">
        <h2 class="card-title mb-4">Profile Information</h2>

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
              <span class="label-text">Username</span>
            </label>
            <input
              v-model="profileForm.username"
              type="text"
              class="input input-bordered w-full max-w-md"
              placeholder="Your username"
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
              placeholder="your@email.com"
            />
          </div>

          <div class="pt-4">
            <Button type="submit" variant="primary" :loading="authStore.loading">
              Save Changes
            </Button>
          </div>
        </form>
      </div>
    </div>

    <!-- Security Tab -->
    <div v-if="activeTab === 'security'" class="space-y-6">
      <div class="card bg-base-100 shadow">
        <div class="card-body">
          <h2 class="card-title mb-4">Change Password</h2>

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
                <span class="label-text">Current Password</span>
              </label>
              <input
                v-model="passwordForm.currentPassword"
                type="password"
                class="input input-bordered w-full max-w-md"
                placeholder="Enter current password"
                required
              />
            </div>

            <div class="form-control">
              <label class="label">
                <span class="label-text">New Password</span>
              </label>
              <input
                v-model="passwordForm.newPassword"
                type="password"
                class="input input-bordered w-full max-w-md"
                placeholder="Enter new password"
                minlength="8"
                required
              />
            </div>

            <div class="form-control">
              <label class="label">
                <span class="label-text">Confirm New Password</span>
              </label>
              <input
                v-model="passwordForm.confirmPassword"
                type="password"
                class="input input-bordered w-full max-w-md"
                :class="{ 'input-error': passwordForm.confirmPassword && !passwordMatch }"
                placeholder="Confirm new password"
                required
              />
              <label v-if="passwordForm.confirmPassword && !passwordMatch" class="label">
                <span class="label-text-alt text-error">Passwords do not match</span>
              </label>
            </div>

            <div class="pt-4">
              <Button
                type="submit"
                variant="primary"
                :loading="authStore.loading"
                :disabled="!passwordMatch"
              >
                Change Password
              </Button>
            </div>
          </form>
        </div>
      </div>

      <div class="card bg-base-100 shadow">
        <div class="card-body">
          <h2 class="card-title text-error mb-4">Danger Zone</h2>
          <p class="text-base-content/60 mb-4">
            Once you log out, you'll need to sign in again to access your account.
          </p>
          <Button @click="handleLogout" variant="error">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Log Out
          </Button>
        </div>
      </div>
    </div>

    <!-- Preferences Tab -->
    <div v-if="activeTab === 'preferences'" class="card bg-base-100 shadow">
      <div class="card-body">
        <h2 class="card-title mb-4">Preferences</h2>

        <form @submit.prevent="savePreferences" class="space-y-6">
          <!-- Theme -->
          <div class="form-control">
            <label class="label">
              <span class="label-text">Theme</span>
            </label>
            <div class="flex gap-4">
              <label class="label cursor-pointer gap-2">
                <input
                  v-model="preferences.theme"
                  type="radio"
                  value="light"
                  class="radio radio-primary"
                />
                <span class="label-text">Light</span>
              </label>
              <label class="label cursor-pointer gap-2">
                <input
                  v-model="preferences.theme"
                  type="radio"
                  value="dark"
                  class="radio radio-primary"
                />
                <span class="label-text">Dark</span>
              </label>
            </div>
          </div>

          <!-- Cards per session -->
          <div class="form-control">
            <label class="label">
              <span class="label-text">Cards per review session</span>
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
              <span class="label-text">Show timer during reviews</span>
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
              <span class="label-text">Auto-play audio on cards</span>
            </label>
          </div>

          <!-- Language -->
          <div class="form-control">
            <label class="label">
              <span class="label-text">Interface Language</span>
            </label>
            <select v-model="preferences.language" class="select select-bordered w-full max-w-md">
              <option value="en">English</option>
              <option value="es">Spanish</option>
              <option value="fr">French</option>
              <option value="de">German</option>
              <option value="ru">Russian</option>
            </select>
          </div>

          <div class="pt-4">
            <Button type="submit" variant="primary">Save Preferences</Button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
