<template>
  <nav
    class="hidden md:flex flex-col h-full w-64 flex-shrink-0 bg-surface-container-lowest border-r border-outline-variant"
  >
    <div class="px-4 py-6 flex flex-col items-start gap-4">
      <div class="flex items-center gap-3">
        <div
          class="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-on-primary font-display-lg text-[26px] leading-none font-bold"
        >
          Z
        </div>
        <div>
          <h1 class="font-display-lg text-[20px] leading-none text-primary font-bold">Zenith AI</h1>
          <p class="font-label-sm text-label-sm text-on-surface-variant mt-1">智能助手</p>
        </div>
      </div>

      <button
        class="w-full bg-primary text-on-primary rounded-lg py-3 px-4 flex items-center justify-center gap-2 border border-transparent hover:bg-surface-container-low hover:text-primary hover:border-outline-variant transition-colors"
        type="button"
        @click="onNewConversation"
      >
        <MaterialIcon name="add" class="text-[20px]" />
        <span class="font-title-sm text-title-sm">新建对话</span>
      </button>

      <button
        class="w-full min-h-[46px] bg-surface-container-lowest text-on-surface-variant rounded-lg py-2.5 px-4 flex items-center justify-center gap-2 border border-outline-variant hover:bg-surface-container hover:text-primary transition-colors disabled:opacity-60"
        type="button"
        :disabled="workspaceLoading"
        :title="workspaceTitle"
        @click="onSelectWorkspace"
      >
        <MaterialIcon
          :name="workspacePath ? 'folder_open' : 'account_tree'"
          class="text-[20px] flex-shrink-0"
        />
        <span class="font-title-sm text-title-sm truncate">{{ workspaceButtonText }}</span>
      </button>

      <div v-if="workspacePath" class="w-full flex items-center justify-start gap-1.5">
        <p
          class="max-w-[calc(100%-34px)] max-h-16 overflow-y-auto break-all font-label-sm text-label-sm text-on-surface-variant leading-snug"
          :title="workspacePath"
        >
          {{ workspacePath }}
        </p>
        <button
          class="w-8 h-8 flex-shrink-0 rounded-full bg-surface-container-low text-on-surface-variant flex items-center justify-center hover:bg-surface-container hover:text-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          type="button"
          :disabled="workspaceOpening"
          :title="workspaceOpening ? '打开中...' : '打开工作目录'"
          @click="onOpenWorkspace"
        >
          <MaterialIcon name="open_in_new" class="text-[18px]" />
        </button>
      </div>

      <p
        v-if="workspaceError"
        class="w-full font-label-sm text-label-sm text-error leading-snug"
      >
        {{ workspaceError }}
      </p>
    </div>

    <div class="flex-1 overflow-y-auto px-2">
      <div class="px-2 pb-2">
        <p class="font-label-sm text-label-sm text-on-surface-variant mb-2 mt-2">历史记录</p>

        <div v-if="conversationStore.sortedConversations.length" class="space-y-1">
          <router-link
            v-for="conversation in conversationStore.sortedConversations"
            :key="conversation.id"
            :to="{ name: 'Chat', query: { conversationId: conversation.id } }"
            class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all"
            :class="
              isConversationActive(conversation.id)
                ? 'text-primary font-semibold bg-surface-container-high'
                : 'text-on-surface-variant hover:bg-surface-container'
            "
            @click="conversationStore.selectConversation(conversation.id)"
          >
            <MaterialIcon
              name="chat_bubble_outline"
              class="text-[18px] flex-shrink-0"
              :fill="isConversationActive(conversation.id) ? 1 : 0"
            />
            <span class="font-body-md text-body-md truncate">{{ conversation.title }}</span>
          </router-link>
        </div>

        <div
          v-else
          class="px-3 py-3 rounded-lg text-on-surface-variant bg-surface-container-low font-body-md text-body-md"
        >
          暂无历史对话
        </div>
      </div>
    </div>

    <div class="mt-auto flex flex-col px-2 pb-4 space-y-1 pt-2">
      <router-link
        v-for="item in utilityNavItems"
        :key="item.name"
        :to="{ name: item.name }"
        class="flex items-center gap-3 px-3 py-2 rounded-lg transition-all"
        :class="
          isActiveRoute(item.name)
            ? 'text-primary font-semibold bg-surface-container-high'
            : 'text-on-surface-variant hover:bg-surface-container'
        "
      >
        <MaterialIcon
          :name="item.icon"
          class="text-[20px]"
          :fill="isActiveRoute(item.name) ? 1 : 0"
        />
        <span class="font-body-md text-body-md">{{ item.label }}</span>
      </router-link>

      <div
        class="flex items-center gap-3 px-2 py-3 rounded-lg cursor-pointer hover:bg-surface-container transition-all mt-2 border-t border-outline-variant/30 pt-4"
      >
        <div
          class="w-8 h-8 rounded-full bg-surface-variant flex items-center justify-center overflow-hidden"
        >
          <MaterialIcon name="account_circle" class="text-on-surface-variant" />
        </div>
        <div class="flex-1 overflow-hidden">
          <p class="font-body-md text-body-md text-on-surface truncate">{{ userStore.userName }}</p>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MaterialIcon from '@components/MaterialIcon.vue'
import { getAppSettings, updateAppSettings } from '@api/localAgent'
import { useConversationStore } from '@store/useConversationStore'
import { useUserStore } from '@store/useUserStore'

const route = useRoute()
const router = useRouter()
const conversationStore = useConversationStore()
const userStore = useUserStore()
const workspacePath = ref('')
const workspaceLoading = ref(false)
const workspaceOpening = ref(false)
const workspaceError = ref('')

const utilityNavItems = [
  { name: 'Tasks', label: '任务', icon: 'assignment' },
  { name: 'Knowledge', label: '知识库', icon: 'database' },
  { name: 'Settings', label: '设置', icon: 'settings' }
]

const currentConversationId = computed(() => {
  const routeConversationId = route.query.conversationId
  return typeof routeConversationId === 'string'
    ? routeConversationId
    : conversationStore.activeConversationId
})

const isConversationActive = (conversationId: string): boolean =>
  route.name === 'Chat' && currentConversationId.value === conversationId

const isActiveRoute = (name: string): boolean => route.name === name

const workspaceButtonText = computed(() =>
  workspaceLoading.value ? '选择中...' : '选择工作空间'
)

const workspaceTitle = computed(() => workspacePath.value || '选择工作空间')

const onNewConversation = (): void => {
  const conversationId = conversationStore.createConversation()
  void router.push({ name: 'Chat', query: { conversationId } })
}

const loadWorkspace = async (): Promise<void> => {
  try {
    const settings = await getAppSettings()
    workspacePath.value = settings.workspace_path
  } catch (error) {
    workspaceError.value = error instanceof Error ? error.message : '工作空间加载失败'
  }
}

const normalizeSelectedWorkspace = (value: unknown): string => {
  if (typeof value === 'string') {
    return value
  }

  if (value && typeof value === 'object') {
    const filePaths = (value as { filePaths?: unknown }).filePaths
    if (Array.isArray(filePaths) && typeof filePaths[0] === 'string') {
      return filePaths[0]
    }
  }

  return ''
}

const onSelectWorkspace = async (): Promise<void> => {
  workspaceError.value = ''
  workspaceLoading.value = true
  try {
    if (!window.api?.selectWorkspace) {
      workspaceError.value = '当前环境不支持选择工作空间'
      return
    }

    const selectedPath = normalizeSelectedWorkspace(await window.api.selectWorkspace())
    if (!selectedPath) {
      return
    }

    const settings = await updateAppSettings({ workspace_path: selectedPath })
    workspacePath.value = settings.workspace_path
  } catch (error) {
    workspaceError.value = error instanceof Error ? error.message : '工作空间选择失败'
  } finally {
    workspaceLoading.value = false
  }
}

const onOpenWorkspace = async (): Promise<void> => {
  workspaceError.value = ''
  if (!workspacePath.value) {
    workspaceError.value = '请先选择工作空间'
    return
  }
  if (!window.api?.openWorkspace) {
    workspaceError.value = '当前环境不支持打开工作目录'
    return
  }

  workspaceOpening.value = true
  try {
    await window.api.openWorkspace(workspacePath.value)
  } catch (error) {
    workspaceError.value = error instanceof Error ? error.message : '工作目录打开失败'
  } finally {
    workspaceOpening.value = false
  }
}

onMounted(() => {
  void loadWorkspace()
})
</script>
