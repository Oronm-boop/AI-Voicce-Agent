<template>
  <div
    class="flex h-screen overflow-hidden text-on-surface bg-background font-body-md text-body-md antialiased"
  >
    <SideNav />
    <div class="flex-1 flex flex-col h-full overflow-hidden relative">
      <TopAppBar />
      <main class="flex-1 overflow-y-auto">
        <router-view />
      </main>
      <AppFooter v-if="route.name === 'Tasks'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import SideNav from './SideNav.vue'
import TopAppBar from './TopAppBar.vue'
import AppFooter from './AppFooter.vue'

const route = useRoute()
</script>
