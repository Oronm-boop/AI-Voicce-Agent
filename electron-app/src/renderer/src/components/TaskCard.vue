<template>
  <!-- 已完成态 -->
  <div
    v-if="status === 'done'"
    class="bg-surface rounded-lg border border-surface-variant p-4"
  >
    <div class="flex justify-between items-start mb-3">
      <span
        class="font-label-sm text-label-sm text-on-surface-variant bg-surface-container px-2 py-1 rounded-md"
      >{{ priorityLabel }}</span>
      <MaterialIcon name="check_circle" :fill="1" class="text-outline-variant text-[20px]" />
    </div>
    <h4 class="font-title-sm text-title-sm text-on-surface-variant mb-2 line-through">{{ task.title }}</h4>
    <p class="font-body-md text-body-md text-outline text-[13px] line-clamp-1 mb-4">{{ task.description }}</p>
    <div class="flex justify-end">
      <button
        type="button"
        class="w-8 h-8 rounded-full flex items-center justify-center text-outline hover:text-primary hover:bg-surface-container"
        title="退回待办"
        @click="$emit('status-change', task, 'todo')"
      >
        <MaterialIcon name="undo" class="text-[18px]" />
      </button>
    </div>
  </div>

  <!-- 进行中态(带进度) -->
  <div
    v-else-if="status === 'in_progress'"
    class="bg-surface rounded-lg border border-primary-fixed p-4 hover:shadow-[0px_4px_12px_rgba(0,0,0,0.05)] transition-all cursor-pointer relative overflow-hidden"
  >
    <div
      class="absolute inset-0 bg-gradient-to-r from-transparent via-primary-fixed/20 to-transparent -translate-x-full animate-shimmer"
    ></div>
    <div class="flex justify-between items-start mb-3 relative z-10">
      <span class="font-label-sm text-label-sm text-primary bg-primary-fixed px-2 py-1 rounded-md">{{ priorityLabel }}</span>
      <button
        type="button"
        class="w-8 h-8 rounded-full flex items-center justify-center text-outline-variant hover:text-primary hover:bg-surface-container"
        title="标记完成"
        @click="$emit('status-change', task, 'done')"
      >
        <MaterialIcon name="check_circle" class="text-[20px]" />
      </button>
    </div>
    <h4 class="font-title-sm text-title-sm text-on-surface mb-2 relative z-10">{{ task.title }}</h4>
    <p class="font-body-md text-body-md text-on-surface-variant text-[13px] line-clamp-2 mb-4 relative z-10">
      {{ task.description }}
    </p>
    <div v-if="task.progress != null" class="mb-4 relative z-10">
      <div class="flex justify-between items-center mb-1">
        <span class="font-label-sm text-label-sm text-on-surface-variant">处理进度</span>
        <span class="font-label-sm text-label-sm text-primary">{{ task.progress }}%</span>
      </div>
      <div class="w-full bg-surface-container-high rounded-full h-1.5">
        <div class="bg-primary h-1.5 rounded-full" :style="{ width: task.progress + '%' }"></div>
      </div>
    </div>
    <div class="flex items-center justify-between mt-auto pt-3 border-t border-surface-variant relative z-10">
      <div class="flex items-center gap-2">
        <div class="w-6 h-6 rounded-full bg-primary flex items-center justify-center text-on-primary">
          <MaterialIcon name="sync" class="text-[14px] animate-spin" />
        </div>
        <span class="font-label-sm text-label-sm text-on-surface-variant">处理中</span>
      </div>
      <button
        type="button"
        class="w-8 h-8 rounded-full flex items-center justify-center text-outline-variant hover:text-primary hover:bg-surface-container"
        title="退回待办"
        @click="$emit('status-change', task, 'todo')"
      >
        <MaterialIcon name="undo" class="text-[18px]" />
      </button>
    </div>
  </div>

  <!-- 待执行态 -->
  <div
    v-else
    class="bg-surface rounded-lg border border-surface-variant p-4 hover:bg-surface-container-lowest transition-colors cursor-pointer group shadow-[0px_2px_4px_rgba(0,0,0,0.02)] hover:shadow-[0px_4px_12px_rgba(0,0,0,0.05)]"
  >
    <div class="flex justify-between items-start mb-3">
      <span
        class="font-label-sm text-label-sm px-2 py-1 rounded-md"
        :class="
          task.priority === 'high'
            ? 'text-on-error-container bg-error-container'
            : 'text-on-surface-variant bg-surface-container-high'
        "
      >{{ priorityLabel }}</span>
      <button
        type="button"
        class="w-8 h-8 rounded-full flex items-center justify-center text-outline-variant group-hover:text-primary hover:bg-surface-container"
        title="开始执行"
        @click="$emit('status-change', task, 'in_progress')"
      >
        <MaterialIcon name="play_arrow" class="text-[20px]" />
      </button>
    </div>
    <h4 class="font-title-sm text-title-sm text-on-surface mb-2">{{ task.title }}</h4>
    <p class="font-body-md text-body-md text-on-surface-variant text-[13px] line-clamp-2 mb-4">{{ task.description }}</p>
    <div class="flex items-center justify-between mt-auto pt-3 border-t border-surface-variant">
      <div class="flex -space-x-2">
        <div
          class="w-6 h-6 rounded-full bg-primary-container text-on-primary flex items-center justify-center text-[10px] border border-surface"
        >AI</div>
      </div>
      <span class="font-label-sm text-label-sm text-outline flex items-center gap-1">
        <MaterialIcon name="schedule" class="text-[14px]" /> {{ createdLabel }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TaskItem } from '@api/localAgent'
import MaterialIcon from './MaterialIcon.vue'

interface Props {
  task: TaskItem
  status: TaskItem['status']
}

const props = defineProps<Props>()

defineEmits<{
  'status-change': [task: TaskItem, status: TaskItem['status']]
}>()

const priorityLabel = computed(() => {
  if (props.task.priority === 'high') {
    return '高优先级'
  }
  if (props.task.priority === 'low') {
    return '低优先级'
  }
  return '普通'
})

const createdLabel = computed(() => {
  const created = new Date(props.task.created_at)
  if (Number.isNaN(created.getTime())) {
    return '待安排'
  }
  return created.toLocaleDateString('zh-CN', {
    month: 'numeric',
    day: 'numeric'
  })
})
</script>
