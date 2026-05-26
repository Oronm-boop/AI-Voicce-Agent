import type { NavigationGuardWithThis, NavigationHookAfter } from 'vue-router'
import { useUserStore } from '@store/useUserStore'

const PLACEHOLDER_TOKEN = '原始值'

export const beforeEach: NavigationGuardWithThis<undefined> = (to) => {
  const userStore = useUserStore()
  const token = userStore.token
  const isAuthed = !!token && token !== PLACEHOLDER_TOKEN

  if (to.meta?.public) {
    if (to.name === 'Login' && isAuthed) {
      return { name: 'Chat' }
    }
    return true
  }

  if (!isAuthed) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  return true
}

export const afterEach: NavigationHookAfter = () => {
  // reserved for future analytics / title updates
}
