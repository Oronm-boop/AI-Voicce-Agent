<template>
  <label class="relative inline-flex items-center cursor-pointer select-none">
    <input
      type="checkbox"
      class="sr-only peer"
      :checked="modelValue"
      :disabled="disabled"
      @change="onChange"
    />
    <div
      class="w-11 h-6 bg-surface-variant rounded-full transition-colors duration-300 peer-checked:bg-primary peer-disabled:opacity-50"
    >
      <span
        class="block absolute top-[2px] left-[2px] h-5 w-5 rounded-full bg-white border border-outline-variant transition-transform duration-300"
        :class="modelValue ? 'translate-x-5 border-primary' : 'translate-x-0'"
      ></span>
    </div>
  </label>
</template>

<script setup lang="ts">
interface Props {
  modelValue: boolean
  disabled?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'change', value: boolean): void
}>()

const onChange = (e: Event): void => {
  if (props.disabled) return
  const value = (e.target as HTMLInputElement).checked
  emit('update:modelValue', value)
  emit('change', value)
}
</script>
