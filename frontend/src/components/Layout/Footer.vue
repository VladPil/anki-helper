<script setup>
const currentYear = new Date().getFullYear()
</script>

<template>
  <footer class="footer footer-center p-4 bg-base-100 text-base-content border-t border-base-200">
    <aside>
      <p>
        AnkiRAG - AI-Powered Flashcard Learning
        <span class="mx-2">|</span>
        <span class="text-base-content/60">&copy; {{ currentYear }}</span>
      </p>
    </aside>
  </footer>
</template>
