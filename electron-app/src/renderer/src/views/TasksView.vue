<template>
  <div class="overflow-x-auto p-container-padding">
    <div class="mb-gutter flex items-start justify-between gap-4">
      <div>
        <h2 class="font-headline-md text-headline-md text-primary">任务执行看板</h2>
        <p class="font-body-md text-body-md text-on-surface-variant mt-1">
          AI 代理当前正在处理及计划中的工作流
        </p>
      </div>
      <button
        type="button"
        class="w-10 h-10 rounded-full border border-outline-variant bg-surface-container-lowest flex items-center justify-center text-primary hover:bg-surface-container"
        :disabled="loading"
        title="刷新任务"
        @click="loadTasks"
      >
        <MaterialIcon name="refresh" class="text-[20px]" :class="{ 'animate-spin': loading }" />
      </button>
    </div>

    <p v-if="errorMessage" class="mb-4 font-body-sm text-body-sm text-error">
      {{ errorMessage }}
    </p>

    <div class="flex gap-gutter min-w-[900px]">
      <section class="flex-1 flex flex-col bg-surface-container-lowest rounded-lg border border-surface-variant p-4">
        <div class="flex items-center justify-between mb-4 pb-2 border-b border-surface-variant">
          <div class="flex items-center gap-2">
            <div class="w-2 h-2 rounded-full bg-outline"></div>
            <h3 class="font-title-sm text-title-sm text-on-surface">待执行</h3>
          </div>
          <span class="font-label-sm text-label-sm text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full">{{ todoTasks.length }}</span>
        </div>
        <div class="flex-1 overflow-y-auto kanban-col space-y-4 pr-2">
          <TaskCard
            v-for="task in todoTasks"
            :key="task.id"
            :task="task"
            status="todo"
            @status-change="handleStatusChange"
          />
          <EmptyColumn v-if="!loading && todoTasks.length === 0" text="暂无待执行任务" />
        </div>
      </section>

      <section class="flex-1 flex flex-col bg-surface-container-lowest rounded-lg border border-surface-variant p-4">
        <div class="flex items-center justify-between mb-4 pb-2 border-b border-surface-variant">
          <div class="flex items-center gap-2">
            <div class="relative w-2 h-2 rounded-full bg-primary">
              <div class="absolute inset-0 rounded-full bg-primary animate-ping opacity-75"></div>
            </div>
            <h3 class="font-title-sm text-title-sm text-primary">执行中</h3>
          </div>
          <span class="font-label-sm text-label-sm text-primary bg-primary-fixed px-2 py-0.5 rounded-full">{{ doingTasks.length }}</span>
        </div>
        <div class="flex-1 overflow-y-auto kanban-col space-y-4 pr-2">
          <TaskCard
            v-for="task in doingTasks"
            :key="task.id"
            :task="task"
            status="in_progress"
            @status-change="handleStatusChange"
          />
          <EmptyColumn v-if="!loading && doingTasks.length === 0" text="暂无执行中任务" />
        </div>
      </section>

      <section class="flex-1 flex flex-col bg-surface-container-lowest rounded-lg border border-surface-variant p-4 opacity-80">
        <div class="flex items-center justify-between mb-4 pb-2 border-b border-surface-variant">
          <div class="flex items-center gap-2">
            <div class="w-2 h-2 rounded-full bg-outline-variant"></div>
            <h3 class="font-title-sm text-title-sm text-on-surface-variant">已完成</h3>
          </div>
          <span class="font-label-sm text-label-sm text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full">{{ doneTasks.length }}</span>
        </div>
        <div class="flex-1 overflow-y-auto kanban-col space-y-4 pr-2">
          <TaskCard
            v-for="task in doneTasks"
            :key="task.id"
            :task="task"
            status="done"
            @status-change="handleStatusChange"
          />
          <EmptyColumn v-if="!loading && doneTasks.length === 0" text="暂无已完成任务" />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import MaterialIcon from '@components/MaterialIcon.vue'
import TaskCard from '@components/TaskCard.vue'
import { getTasks, updateTask, type TaskItem } from '@api/localAgent'

const tasks = ref<TaskItem[]>([])
const loading = ref(false)
const errorMessage = ref('')

const todoTasks = computed(() => tasks.value.filter((task) => task.status === 'todo'))
const doingTasks = computed(() => tasks.value.filter((task) => task.status === 'in_progress'))
const doneTasks = computed(() => tasks.value.filter((task) => task.status === 'done'))

const EmptyColumn = defineComponent({
  props: {
    text: {
      type: String,
      required: true
    }
  },
  setup(props) {
    return () =>
      h(
        'div',
        {
          class:
            'min-h-[120px] rounded-lg border border-dashed border-outline-variant flex items-center justify-center text-body-sm text-on-surface-variant'
        },
        props.text
      )
  }
})

const loadTasks = async (): Promise<void> => {
  loading.value = true
  errorMessage.value = ''
  try {
    tasks.value = await getTasks()
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    errorMessage.value = `任务加载失败：${message}`
  } finally {
    loading.value = false
  }
}

const replaceTask = (updated: TaskItem): void => {
  const index = tasks.value.findIndex((task) => task.id === updated.id)
  if (index >= 0) {
    tasks.value[index] = updated
  }
}

const handleStatusChange = async (
  task: TaskItem,
  status: TaskItem['status']
): Promise<void> => {
  errorMessage.value = ''
  const progress = status === 'done' ? 100 : status === 'in_progress' ? Math.max(task.progress, 10) : 0
  try {
    const updated = await updateTask(task.id, { status, progress })
    replaceTask(updated)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    errorMessage.value = `任务更新失败：${message}`
  }
}

onMounted(() => {
  void loadTasks()
})
</script>
