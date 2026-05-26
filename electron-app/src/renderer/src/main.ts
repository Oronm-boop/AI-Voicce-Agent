import { createApp } from 'vue'
import App from './App.vue'

//全局样式 + Tailwind
import '@renderer/assets/css/styles.less'

//路由
import router from './router'

//状态管理
import { createPinia } from 'pinia'
import piniaPluginPersist from 'pinia-plugin-persist'
const store = createPinia()
store.use(piniaPluginPersist)

createApp(App).use(router).use(store).mount('#app')