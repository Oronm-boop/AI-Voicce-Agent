<template>
  <div class="wave-container" :class="{ 'opacity-30': !active }">
    <div v-for="i in count" :key="i" class="wave-line"></div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  count?: number
  active?: boolean
}

withDefaults(defineProps<Props>(), {
  count: 10,
  active: true
})
</script>
