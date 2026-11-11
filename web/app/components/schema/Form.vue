<script setup lang="ts">
import type { JsonSchema } from '~/utils/schema'

const props = defineProps<{
  schema: JsonSchema
  modelValue: Record<string, unknown>
  errors?: Record<string, string>
}>()
const emit = defineEmits<{ 'update:modelValue': [value: Record<string, unknown>] }>()

const properties = computed(() => resolveSchema(props.schema, props.schema)[0].properties ?? {})
</script>

<template>
  <div class="grid gap-5">
    <SchemaField
      v-for="(child, key) in properties"
      :key="key"
      :name="String(key)"
      :path="String(key)"
      :schema="child"
      :root="schema"
      :model-value="modelValue[String(key)]"
      :errors="errors ?? {}"
      @update:model-value="emit('update:modelValue', { ...modelValue, [String(key)]: $event })"
    />
  </div>
</template>
