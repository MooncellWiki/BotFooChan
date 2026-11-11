<script setup lang="ts">
withDefaults(defineProps<{
  message: string
  label?: string
  icon?: string
  confirmLabel?: string
  loading?: boolean
}>(), { label: undefined, icon: 'i-lucide-trash-2', confirmLabel: '确定', loading: false })
const emit = defineEmits<{ confirm: [] }>()
const open = ref(false)

function confirm() {
  open.value = false
  emit('confirm')
}
</script>

<template>
  <UPopover v-model:open="open">
    <UButton :label="label" :icon="icon" :loading="loading" color="error" variant="ghost" size="sm" :aria-label="label ?? '删除'" />
    <template #content>
      <div class="flex max-w-72 flex-col gap-3 p-3">
        <p class="text-sm">
          {{ message }}
        </p>
        <div class="flex justify-end gap-2">
          <UButton label="取消" size="xs" color="neutral" variant="ghost" @click="open = false" />
          <UButton :label="confirmLabel" size="xs" color="error" @click="confirm" />
        </div>
      </div>
    </template>
  </UPopover>
</template>
