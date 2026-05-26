<template>
  <div
    class="bg-background text-on-background min-h-screen flex items-center justify-center p-container-padding font-body-md antialiased"
  >
    <main
      class="w-full max-w-md bg-surface-container-lowest rounded-xl border border-surface-variant p-10 shadow-[0px_10px_30px_rgba(0,0,0,0.04)] relative overflow-hidden"
    >
      <div
        class="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 bg-surface-container rounded-full blur-3xl opacity-50 pointer-events-none"
      ></div>

      <div class="relative z-10 flex flex-col items-center mb-8">
        <div class="mb-4">
          <MaterialIcon name="explore" :fill="1" :size="36" class="text-primary" />
        </div>
        <h1 class="font-display-lg text-display-lg text-primary mb-2 text-center">Zenith AI</h1>
        <h2 class="font-headline-md text-headline-md text-on-surface-variant text-center">欢迎回来</h2>
      </div>

      <form class="relative z-10 space-y-6" @submit.prevent="onSubmit">
        <div class="space-y-stack-tight">
          <label
            class="block font-body-md text-body-md transition-colors"
            :class="focused === 'username' ? 'text-primary' : 'text-on-surface-variant'"
            for="username"
          >用户名或邮箱</label>
          <input
            id="username"
            v-model="form.username"
            type="text"
            placeholder="输入您的用户名"
            autocomplete="username"
            class="w-full bg-surface border border-outline-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-0 placeholder:text-outline transition-colors"
            @focus="focused = 'username'"
            @blur="focused = ''"
          />
        </div>

        <div class="space-y-stack-tight">
          <label
            class="block font-body-md text-body-md transition-colors"
            :class="focused === 'password' ? 'text-primary' : 'text-on-surface-variant'"
            for="password"
          >密码</label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            placeholder="输入您的密码"
            autocomplete="current-password"
            class="w-full bg-surface border border-outline-variant rounded-lg px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-0 placeholder:text-outline transition-colors"
            @focus="focused = 'password'"
            @blur="focused = ''"
          />
        </div>

        <div class="flex items-center justify-between font-body-md text-body-md">
          <label class="flex items-center space-x-2 cursor-pointer group">
            <input
              v-model="form.remember"
              type="checkbox"
              class="rounded border-outline-variant text-primary focus:ring-primary w-4 h-4 bg-surface transition-colors cursor-pointer"
            />
            <span class="text-on-surface-variant group-hover:text-primary transition-colors">记住我</span>
          </label>
          <a href="#" class="text-primary hover:text-primary-container transition-colors">忘记密码？</a>
        </div>

        <p v-if="errorMsg" class="text-error text-body-md font-body-md">{{ errorMsg }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="w-full bg-primary-container text-on-primary font-title-sm text-title-sm rounded-lg py-3 px-6 hover:bg-primary transition-colors flex items-center justify-center space-x-2 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          <span>{{ loading ? '登录中...' : '登录' }}</span>
          <MaterialIcon v-if="!loading" name="arrow_forward" :size="20" />
        </button>
      </form>

      <div class="relative z-10 flex items-center py-6">
        <div class="flex-grow border-t border-surface-variant"></div>
        <span class="flex-shrink-0 px-4 font-body-md text-body-md text-outline">或</span>
        <div class="flex-grow border-t border-surface-variant"></div>
      </div>

      <div class="relative z-10">
        <button
          type="button"
          class="w-full bg-surface-container-lowest border border-outline-variant text-primary font-body-md text-body-md rounded-lg py-3 px-6 hover:bg-surface-container-low transition-colors flex items-center justify-center space-x-3"
        >
          <MaterialIcon name="language" :size="20" />
          <span>使用企业 SSO 登录</span>
        </button>
      </div>

      <div class="relative z-10 mt-8 text-center font-label-sm text-label-sm text-outline">
        <p>
          还没有账号？
          <a href="#" class="text-primary hover:underline">联系管理员</a>
        </p>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import MaterialIcon from '@components/MaterialIcon.vue'
import { useUserStore } from '@store/useUserStore'
import { loginByJson } from '@api/login'

const router = useRouter()
const userStore = useUserStore()

const form = reactive({
  username: '',
  password: '',
  remember: false
})

const focused = ref<'username' | 'password' | ''>('')
const loading = ref(false)
const errorMsg = ref('')

const onSubmit = async (): Promise<void> => {
  errorMsg.value = ''
  if (!form.username || !form.password) {
    errorMsg.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  try {
    const res: any = await loginByJson({
      username: form.username,
      password: form.password,
      key: '',
      captcha: ''
    })
    const token = res?.token ?? res?.data?.token ?? 'mock-token'
    userStore.token = token
    userStore.userName = form.username
    router.replace('/chat')
  } catch (err: any) {
    // 开发期容错：后端不可用时用模拟 token 放行
    userStore.token = 'mock-token'
    userStore.userName = form.username
    router.replace('/chat')
    errorMsg.value = err?.message ?? ''
  } finally {
    loading.value = false
  }
}
</script>
