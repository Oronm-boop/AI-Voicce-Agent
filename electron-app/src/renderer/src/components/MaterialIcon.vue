<template>
  <span
    class="material-symbols-outlined"
    :style="iconStyle"
    :class="sizeClass"
  >{{ name }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  name: string
  fill?: 0 | 1
  weight?: number
  size?: number | string
}

const props = withDefaults(defineProps<Props>(), {
  fill: 0,
  weight: 400,
  size: undefined
})

const iconStyle = computed(() => {
  const style: Record<string, string> = {
    fontVariationSettings: `'FILL' ${props.fill}, 'wght' ${props.weight}, 'GRAD' 0, 'opsz' 24`
  }
  if (typeof props.size === 'number') {
    style.fontSize = `${props.size}px`
  } else if (typeof props.size === 'string') {
    style.fontSize = props.size
  }
  return style
})

const sizeClass = computed(() => (props.size ? '' : ''))
</script>
