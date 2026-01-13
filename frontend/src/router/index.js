import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Lazy load views for better performance
const DashboardView = () => import('@/views/DashboardView.vue')
const LoginView = () => import('@/views/LoginView.vue')
const RegisterView = () => import('@/views/RegisterView.vue')
const DecksView = () => import('@/views/DecksView.vue')
const DeckDetailView = () => import('@/views/DeckDetailView.vue')
const GenerateView = () => import('@/views/GenerateView.vue')
const ChatView = () => import('@/views/ChatView.vue')
const SettingsView = () => import('@/views/SettingsView.vue')

const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: DashboardView,
    meta: { requiresAuth: true, title: 'Dashboard' }
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { guest: true, title: 'Login' }
  },
  {
    path: '/register',
    name: 'register',
    component: RegisterView,
    meta: { guest: true, title: 'Register' }
  },
  {
    path: '/decks',
    name: 'decks',
    component: DecksView,
    meta: { requiresAuth: true, title: 'My Decks' }
  },
  {
    path: '/decks/:id',
    name: 'deck-detail',
    component: DeckDetailView,
    meta: { requiresAuth: true, title: 'Deck' },
    props: true
  },
  {
    path: '/generate',
    name: 'generate',
    component: GenerateView,
    meta: { requiresAuth: true, title: 'Generate Cards' }
  },
  {
    path: '/chat',
    name: 'chat',
    component: ChatView,
    meta: { requiresAuth: true, title: 'AI Chat' }
  },
  {
    path: '/settings',
    name: 'settings',
    component: SettingsView,
    meta: { requiresAuth: true, title: 'Settings' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    } else {
      return { top: 0 }
    }
  }
})

// Navigation guards
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // Update document title
  document.title = to.meta.title ? `${to.meta.title} | AnkiRAG` : 'AnkiRAG'

  // Initialize auth state if needed
  if (authStore.token && !authStore.user) {
    await authStore.fetchProfile()
  }

  // Check if route requires authentication
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return next({
      name: 'login',
      query: { redirect: to.fullPath }
    })
  }

  // Check if route is for guests only
  if (to.meta.guest && authStore.isAuthenticated) {
    return next({ name: 'dashboard' })
  }

  next()
})

export default router
