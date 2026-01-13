<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import Button from '@/components/Common/Button.vue'
import Alert from '@/components/Common/Alert.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const uiStore = useUiStore()

const form = ref({
  email: '',
  password: ''
})

const showPassword = ref(false)
const rememberMe = ref(false)

const isValid = computed(() => {
  return form.value.email && form.value.password
})

async function handleSubmit() {
  if (!isValid.value) return

  const success = await authStore.login(form.value)

  if (success) {
    uiStore.notifySuccess('Welcome back!')
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  }
}
</script>

<template>
  <div class="card w-full max-w-md bg-base-100 shadow-xl">
    <div class="card-body">
      <div class="text-center mb-6">
        <h1 class="text-3xl font-bold text-primary">AnkiRAG</h1>
        <p class="text-base-content/60 mt-2">Sign in to your account</p>
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
            <span class="label-text">Email</span>
          </label>
          <input
            v-model="form.email"
            type="email"
            placeholder="your@email.com"
            class="input input-bordered w-full"
            :class="{ 'input-error': authStore.error }"
            required
            autocomplete="email"
          />
        </div>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Password</span>
          </label>
          <div class="relative">
            <input
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="Enter your password"
              class="input input-bordered w-full pr-10"
              :class="{ 'input-error': authStore.error }"
              required
              autocomplete="current-password"
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
        </div>

        <div class="flex items-center justify-between">
          <label class="label cursor-pointer gap-2">
            <input
              v-model="rememberMe"
              type="checkbox"
              class="checkbox checkbox-primary checkbox-sm"
            />
            <span class="label-text">Remember me</span>
          </label>
          <a href="#" class="link link-primary text-sm">Forgot password?</a>
        </div>

        <Button
          type="submit"
          variant="primary"
          class="w-full"
          :loading="authStore.loading"
          :disabled="!isValid"
        >
          Sign In
        </Button>
      </form>

      <div class="divider">OR</div>

      <p class="text-center text-base-content/60">
        Don't have an account?
        <router-link to="/register" class="link link-primary">Sign up</router-link>
      </p>
    </div>
  </div>
</template>
