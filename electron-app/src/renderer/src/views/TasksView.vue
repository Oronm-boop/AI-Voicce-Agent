<template>
  <div class="overflow-x-auto p-container-padding">
    <div class="mb-gutter">
      <h2 class="font-headline-md text-headline-md text-primary">任务执行看板</h2>
      <p class="font-body-md text-body-md text-on-surface-variant mt-1">
        AI 代理当前正在处理及计划中的工作流
      </p>
    </div>

    <div class="flex gap-gutter min-w-[900px]">
      <!-- 待执行 -->
      <div
        class="flex-1 flex flex-col bg-surface-container-lowest rounded-xl border border-surface-variant p-4"
      >
        <div
          class="flex items-center justify-between mb-4 pb-2 border-b border-surface-variant"
        >
          <div class="flex items-center gap-2">
            <div class="w-2 h-2 rounded-full bg-outline"></div>
            <h3 class="font-title-sm text-title-sm text-on-surface">待执行</h3>
          </div>
          <span
            class="font-label-sm text-label-sm text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full"
          >{{ todoTasks.length }}</span>
        </div>
        <div class="flex-1 overflow-y-auto kanban-col space-y-4 pr-2">
          <TaskCard v-for="t in todoTasks" :key="t.id" :task="t" status="todo" />
        </div>
      </div>

      <!-- 执行中 -->
      <div
        class="flex-1 flex flex-col bg-surface-container-lowest rounded-xl border border-surface-variant p-4"
      >
        <div
          class="flex items-center justify-between mb-4 pb-2 border-b border-surface-variant"
        >
          <div class="flex items-center gap-2">
            <div class="relative w-2 h-2 rounded-full bg-primary">
              <div
                class="absolute inset-0 rounded-full bg-primary animate-ping opacity-75"
              ></div>
            </div>
            <h3 class="font-title-sm text-title-sm text-primary">执行中</h3>
          </div>
          <span
            class="font-label-sm text-label-sm text-primary bg-primary-fixed px-2 py-0.5 rounded-full"
          >{{ doingTasks.length }}</span>
        </div>
        <div class="flex-1 overflow-y-auto kanban-col space-y-4 pr-2">
          <TaskCard v-for="t in doingTasks" :key="t.id" :task="t" status="doing" />
        </div>
      </div>

      <!-- 已完成 -->
      <div
        class="flex-1 flex flex-col bg-surface-container-lowest rounded-xl border border-surface-variant p-4 opacity-70"
      >
        <div
          class="flex items-center justify-between mb-4 pb-2 border-b border-surface-variant"
        >
          <div class="flex items-center gap-2">
            <div class="w-2 h-2 rounded-full bg-outline-variant"></div>
            <h3 class="font-title-sm text-title-sm text-on-surface-variant">已完成</h3>
          </div>
          <span
            class="font-label-sm text-label-sm text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full"
          >{{ doneTasks.length }}</span>
        </div>
        <div class="flex-1 overflow-y-auto kanban-col space-y-4 pr-2">
          <TaskCard v-for="t in doneTasks" :key="t.id" :task="t" status="done" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import TaskCard, { type TaskItem } from '@components/TaskCard.vue'

const todoTasks = ref<TaskItem[]>([
  {
    id: 't1',
    tag: '文本处理',
    title: '整理今日会议摘要',
    desc: '提取产品战略会议中的关键决策点和后续行动项，生成结构化文档。',
    dueLabel: '今天'
  },
  {
    id: 't2',
    tag: '高优先级',
    title: '预定上海机票',
    desc: '搜索并预定下周二前往上海的早班机票，优选东航。',
    dueLabel: '明天',
    priority: 'high'
  },
  {
    id: 't3',
    tag: '研究',
    title: '收集竞品定价资料',
    desc: '汇总同行业 5 家头部产品的最新定价与优惠政策。',
    dueLabel: '本周'
  }
])

const doingTasks = ref<TaskItem[]>([
  {
    id: 'd1',
    tag: '数据分析',
    title: '分析竞品数据',
    desc: '抓取 Q3 财报数据并生成可视化对比图表。',
    progress: 65
  }
])

const doneTasks = ref<TaskItem[]>([
  {
    id: 'c1',
    tag: '邮件',
    title: '回复客户咨询邮件',
    desc: '已发送标准报价单及合作协议。'
  },
  {
    id: 'c2',
    tag: '系统',
    title: '清理本地缓存文件',
    desc: '释放 2.4GB 空间。'
  }
])
</script>
