<template>
  <header
    class="flex justify-between items-center w-full px-container-padding h-16 bg-surface border-b border-outline-variant sticky top-0 z-20 flex-shrink-0"
  >
    <div class="flex items-center gap-4 md:hidden">
      <MaterialIcon name="menu" class="text-on-surface-variant cursor-pointer" />
      <span class="font-display-lg text-[20px] font-bold text-primary">Zenith AI</span>
    </div>
    <div class="hidden md:block flex-1"></div>
    <div class="flex items-center gap-2">
      <button
        class="w-10 h-10 rounded-full flex items-center justify-center text-primary hover:bg-surface-container-low transition-colors duration-200 active:scale-95"
        @click="onAccountClick"
      >
        <MaterialIcon name="account_circle" />
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import MaterialIcon from '@components/MaterialIcon.vue'
import { useUserStore } from '@store/useUserStore'

const router = useRouter()
const userStore = useUserStore()

const onAccountClick = (): void => {
  userStore.token = ''
  router.replace('/login')
}
</script>
