<template>
  <div class="px-container-padding py-10 max-w-[1200px] mx-auto w-full">
    <div class="mb-10 animate-fade-in-up">
      <h2 class="font-display-lg text-display-lg text-primary">知识库与技能中心</h2>
      <p class="font-body-lg text-body-lg text-on-surface-variant mt-2 max-w-2xl">
        配置您的专属 AI 能力。启用特定技能以扩展代理的功能，并管理您的私有知识文档以实现精准问答。
      </p>
    </div>

    <!-- 技能中心 -->
    <section class="mb-14">
      <div class="flex items-center justify-between mb-6">
        <h3 class="font-headline-md text-headline-md text-primary flex items-center gap-2">
          <MaterialIcon name="bolt" class="text-on-surface-variant" />
          技能中心
        </h3>
        <span
          class="font-label-sm text-label-sm px-3 py-1 bg-surface-container-high rounded-full text-on-surface-variant"
        >{{ activeSkillsCount }} Active</span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="skill in skills"
          :key="skill.id"
          class="bg-surface-container-lowest border border-outline-variant rounded-xl p-6 hover:shadow-[0_10px_30px_rgba(0,0,0,0.04)] transition-all duration-300 relative group overflow-hidden"
        >
          <div
            class="absolute top-0 right-0 w-32 h-32 bg-primary-fixed opacity-10 rounded-full -translate-y-1/2 translate-x-1/2 group-hover:scale-150 transition-transform duration-500"
          ></div>
          <div class="flex justify-between items-start mb-4 relative z-10">
            <div class="w-12 h-12 rounded-lg bg-surface-container flex items-center justify-center">
              <MaterialIcon :name="skill.icon" :size="24" class="text-primary" />
            </div>
            <ToggleSwitch v-model="skill.enabled" />
          </div>
          <div class="relative z-10">
            <h4 class="font-title-sm text-title-sm text-primary mb-2">{{ skill.name }}</h4>
            <p class="font-body-md text-body-md text-on-surface-variant line-clamp-2">{{ skill.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 我的文档 -->
    <section>
      <div class="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
        <h3 class="font-headline-md text-headline-md text-primary flex items-center gap-2">
          <MaterialIcon name="folder_special" class="text-on-surface-variant" />
          我的文档
        </h3>
        <button
          type="button"
          class="bg-surface-container-lowest border border-outline-variant text-primary rounded-lg py-2 px-4 font-title-sm text-title-sm flex justify-center items-center gap-2 hover:bg-surface-container-low transition-colors"
          @click="onUpload"
        >
          <MaterialIcon name="upload" :size="18" />
          上传新文档
        </button>
      </div>

      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl overflow-hidden">
        <div
          class="grid grid-cols-12 gap-4 p-4 border-b border-outline-variant bg-surface-container-low/50 font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider"
        >
          <div class="col-span-6 md:col-span-5">文档名称</div>
          <div class="col-span-3 hidden md:block">大小</div>
          <div class="col-span-3 hidden md:block">状态</div>
          <div class="col-span-6 md:col-span-1 text-right">操作</div>
        </div>

        <div class="divide-y divide-outline-variant/50">
          <div
            v-for="doc in documents"
            :key="doc.id"
            class="grid grid-cols-12 gap-4 p-4 items-center hover:bg-surface-container-low/30 transition-colors group"
          >
            <div class="col-span-8 md:col-span-5 flex items-center gap-3">
              <MaterialIcon :name="doc.icon" class="text-primary-container opacity-70" />
              <span class="font-body-md text-body-md text-on-surface truncate">{{ doc.name }}</span>
            </div>
            <div class="col-span-3 hidden md:block font-body-md text-body-md text-on-surface-variant">
              {{ doc.size }}
            </div>
            <div class="col-span-3 hidden md:flex items-center gap-2">
              <span class="w-2 h-2 rounded-full" :class="statusDotClass(doc.status)"></span>
              <span class="font-body-md text-body-md text-on-surface-variant">{{ statusLabel(doc.status) }}</span>
            </div>
            <div
              class="col-span-4 md:col-span-1 flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <button
                type="button"
                class="p-1.5 text-on-surface-variant hover:text-primary hover:bg-surface-container rounded-md transition-colors"
                title="重新索引"
                @click="onReindex(doc.id)"
              >
                <MaterialIcon name="sync" :size="18" />
              </button>
              <button
                type="button"
                class="p-1.5 text-on-surface-variant hover:text-error hover:bg-error-container rounded-md transition-colors"
                title="删除"
                @click="onDelete(doc.id)"
              >
                <MaterialIcon name="delete" :size="18" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import MaterialIcon from '@components/MaterialIcon.vue'
import ToggleSwitch from '@components/ToggleSwitch.vue'

interface Skill {
  id: string
  name: string
  icon: string
  desc: string
  enabled: boolean
}

interface Doc {
  id: string
  name: string
  icon: string
  size: string
  status: 'ready' | 'indexing' | 'error'
}

const skills = ref<Skill[]>([
  {
    id: 's1',
    name: 'PDF 文档解析',
    icon: 'picture_as_pdf',
    desc: '支持深度读取、理解和提取复杂 PDF 文档中的文本、表格和结构化数据。',
    enabled: true
  },
  {
    id: 's2',
    name: 'Web 自动化搜索',
    icon: 'travel_explore',
    desc: '允许代理自主访问互联网，检索最新资讯并整合多源信息提供准确回答。',
    enabled: true
  },
  {
    id: 's3',
    name: '代码生成助手',
    icon: 'code',
    desc: '提供高级代码编写、重构建议和 Debug 支持，涵盖多种主流编程语言。',
    enabled: false
  },
  {
    id: 's4',
    name: '日程管理',
    icon: 'event',
    desc: '与日历联动自动安排会议、提醒重要事项，避免时间冲突。',
    enabled: true
  },
  {
    id: 's5',
    name: '邮件智能回复',
    icon: 'mail',
    desc: '基于上下文与历史风格生成商务邮件初稿，支持多语言。',
    enabled: true
  },
  {
    id: 's6',
    name: '语音转写',
    icon: 'graphic_eq',
    desc: '将会议或电话录音实时转写为可检索的结构化文本。',
    enabled: false
  }
])

const documents = ref<Doc[]>([
  {
    id: 'd1',
    name: 'Q3_项目说明书_V2.pdf',
    icon: 'description',
    size: '2.4 MB',
    status: 'ready'
  },
  {
    id: 'd2',
    name: '2023年度财务分析预测.xlsx',
    icon: 'table_view',
    size: '1.1 MB',
    status: 'indexing'
  },
  {
    id: 'd3',
    name: '客户访谈纪要.docx',
    icon: 'article',
    size: '480 KB',
    status: 'ready'
  }
])

const activeSkillsCount = computed(() => skills.value.filter((s) => s.enabled).length)

const statusDotClass = (s: Doc['status']): string => {
  if (s === 'ready') return 'bg-primary'
  if (s === 'indexing') return 'bg-surface-tint animate-pulse'
  return 'bg-error'
}

const statusLabel = (s: Doc['status']): string => {
  if (s === 'ready') return '已就绪'
  if (s === 'indexing') return '索引中...'
  return '错误'
}

const onUpload = (): void => {
  console.log('[Knowledge] upload triggered')
}

const onReindex = (id: string): void => {
  const target = documents.value.find((d) => d.id === id)
  if (target) target.status = 'indexing'
}

const onDelete = (id: string): void => {
  documents.value = documents.value.filter((d) => d.id !== id)
}
</script>
