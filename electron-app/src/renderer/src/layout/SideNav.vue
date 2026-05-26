<template>
  <nav
    class="hidden md:flex flex-col h-full bg-surface-container-lowest border-r border-outline-variant w-64 flex-shrink-0"
  >
    <!-- Brand -->
    <div class="px-4 py-6 flex items-center gap-3">
      <div
        class="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-on-primary"
      >
        <MaterialIcon name="auto_awesome" :fill="1" />
      </div>
      <div>
        <h1 class="font-display-lg text-[24px] leading-tight text-primary font-bold">Zenith AI</h1>
        <p class="font-label-sm text-label-sm text-on-surface-variant">智能助手</p>
      </div>
    </div>

    <!-- New conversation CTA -->
    <div class="px-4 mb-4">
      <button
        class="w-full bg-primary-container text-on-primary rounded-lg py-3 flex items-center justify-center gap-2 hover:bg-primary transition-colors"
        @click="onNewConversation"
      >
        <MaterialIcon name="add" />
        <span class="font-title-sm text-title-sm">新建对话</span>
      </button>
    </div>

    <!-- Nav links -->
    <div class="flex-1 px-2 space-y-1">
      <router-link
        v-for="item in navItems"
        :key="item.name"
        :to="item.path"
        class="flex items-center gap-3 px-4 py-3 rounded-lg transition-all"
        :class="
          isActive(item.name)
            ? 'text-primary font-semibold bg-surface-container-high opacity-90'
            : 'text-on-surface-variant hover:bg-surface-container'
        "
      >
        <MaterialIcon :name="item.icon" :fill="isActive(item.name) ? 1 : 0" />
        <span class="font-title-sm text-title-sm">{{ item.label }}</span>
      </router-link>
    </div>

    <!-- User footer -->
    <div class="mt-auto border-t border-outline-variant px-4 py-4 flex items-center gap-3">
      <div
        class="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center"
      >
        <MaterialIcon name="account_circle" class="text-primary" />
      </div>
      <div class="flex flex-col overflow-hidden">
        <span class="font-title-sm text-title-sm text-primary truncate">{{ userStore.userName }}</span>
        <span class="font-label-sm text-[10px] text-on-surface-variant truncate">admin@zenith.ai</span>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import MaterialIcon from '@components/MaterialIcon.vue'
import { useUserStore } from '@store/useUserStore'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const navItems = [
  { name: 'Chat', label: '对话', icon: 'chat_bubble', path: '/chat' },
  { name: 'Tasks', label: '任务', icon: 'assignment', path: '/tasks' },
  { name: 'Knowledge', label: '知识库', icon: 'database', path: '/knowledge' },
  { name: 'Settings', label: '设置', icon: 'settings', path: '/settings' }
]

const isActive = (name: string): boolean => route.name === name

const onNewConversation = (): void => {
  router.push('/chat')
}
</script>
