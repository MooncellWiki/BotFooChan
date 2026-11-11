<script setup lang="ts">
import type { JsonSchema } from '~/utils/schema'

const props = defineProps<{
  name: string
  path: string
  schema: JsonSchema
  root: JsonSchema
  modelValue: unknown
  errors: Record<string, string>
}>()
const emit = defineEmits<{ 'update:modelValue': [value: unknown] }>()

const resolved = computed(() => resolveSchema(props.schema, props.root))
const field = computed(() => resolved.value[0])
const nullable = computed(() => resolved.value[1])
const kind = computed(() => fieldKind(field.value))
const description = computed(() => field.value.description ?? props.schema.description)

function update(value: unknown) {
  emit('update:modelValue', value)
}

// 数字：空着且可为 null 时提交 null
const numberText = computed({
  get: () => (props.modelValue === null || props.modelValue === undefined ? '' : String(props.modelValue)),
  set: (text: string) => {
    if (text === '') return update(nullable.value ? null : props.modelValue)
    const value = Number(text)
    if (!Number.isNaN(value)) update(kind.value === 'integer' ? Math.trunc(value) : value)
  },
})

// 密钥：打码的原值不显示，留空就是不改，点「清除」才真的清掉
const original = props.modelValue
const hasOriginal = isMasked(original)
const cleared = ref(false)
const secretText = computed({
  get: () => (isMasked(props.modelValue) ? '' : String(props.modelValue ?? '')),
  set: (text: string) => update(text === '' && hasOriginal && !cleared.value ? original : text),
})
function clearSecret() {
  cleared.value = true
  update(nullable.value ? null : '')
}

const enumItems = computed(() => {
  const items = (field.value.enum ?? []).map(v => ({ label: String(v), value: v as string }))
  return nullable.value ? [{ label: '（不设置）', value: '__null__' }, ...items] : items
})
const enumValue = computed({
  get: () => (props.modelValue === null || props.modelValue === undefined ? '__null__' : String(props.modelValue)),
  set: (value: string) => update(value === '__null__' ? null : field.value.enum?.find(v => String(v) === value)),
})

// 其余复杂类型：JSON 文本，失焦时解析
const jsonText = ref('')
const jsonError = ref('')
watch(() => props.modelValue, (value) => {
  if (kind.value === 'json') jsonText.value = JSON.stringify(value ?? null, null, 2)
}, { immediate: true })
function commitJson() {
  try {
    update(JSON.parse(jsonText.value))
    jsonError.value = ''
  }
  catch {
    jsonError.value = '不是合法的 JSON'
  }
}

const childValue = (key: string) => (isPlainObject(props.modelValue) ? props.modelValue[key] : undefined)
function updateChild(key: string, value: unknown) {
  update({ ...(isPlainObject(props.modelValue) ? props.modelValue : {}), [key]: value })
}
</script>

<template>
  <div v-if="kind === 'object'" class="grid gap-4 rounded-md border border-default p-4">
    <div>
      <p class="font-mono text-sm font-medium">
        {{ name }}
      </p>
      <p v-if="description" class="whitespace-pre-line text-xs text-muted">
        {{ description }}
      </p>
    </div>
    <SchemaField
      v-for="(child, key) in field.properties"
      :key="key"
      :name="String(key)"
      :path="`${path}.${key}`"
      :schema="child"
      :root="root"
      :model-value="childValue(String(key))"
      :errors="errors"
      @update:model-value="updateChild(String(key), $event)"
    />
  </div>

  <UFormField
    v-else
    :error="errors[path] || jsonError || undefined"
    :ui="{ label: 'font-mono', description: 'whitespace-pre-line' }"
    :label="name"
    :description="description"
  >
    <template #hint>
      <div class="flex gap-1">
        <UBadge v-if="field.restart || schema.restart" label="重启后生效" color="warning" variant="subtle" size="sm" />
        <UBadge v-if="field.secret || schema.secret" label="密钥" color="neutral" variant="subtle" size="sm" />
        <UBadge v-if="field.model_ref || schema.model_ref" label="模型引用" color="primary" variant="subtle" size="sm" />
      </div>
    </template>

    <USwitch v-if="kind === 'boolean'" :model-value="Boolean(modelValue)" @update:model-value="update" />

    <UInput
      v-else-if="kind === 'integer' || kind === 'number'"
      v-model="numberText"
      type="number"
      :placeholder="nullable ? '不设置' : undefined"
      class="w-48"
    />

    <USelect v-else-if="kind === 'enum'" v-model="enumValue" :items="enumItems" class="w-64" />

    <UInputTags
      v-else-if="kind === 'tags'"
      :model-value="Array.isArray(modelValue) ? modelValue.map(String) : []"
      placeholder="回车添加"
      class="w-full"
      @update:model-value="update"
    />

    <div v-else-if="kind === 'string' && (field.secret || schema.secret)" class="flex items-center gap-2">
      <UInput
        v-model="secretText"
        type="password"
        autocomplete="new-password"
        :placeholder="hasOriginal && !cleared ? '已设置，留空表示不改' : '未设置'"
        class="w-full max-w-md"
      />
      <UButton v-if="hasOriginal && !cleared" label="清除" color="neutral" variant="ghost" size="sm" @click="clearSecret" />
    </div>

    <UTextarea
      v-else-if="kind === 'string' && (field.multiline || schema.multiline)"
      :model-value="String(modelValue ?? '')"
      autoresize
      :rows="3"
      class="w-full"
      @update:model-value="update"
    />

    <UInput
      v-else-if="kind === 'string'"
      :model-value="String(modelValue ?? '')"
      :placeholder="nullable ? '不设置' : undefined"
      class="w-full max-w-xl"
      @update:model-value="(v: string) => update(v === '' && nullable ? null : v)"
    />

    <UTextarea
      v-else
      v-model="jsonText"
      autoresize
      :rows="4"
      class="w-full font-mono text-xs"
      @blur="commitJson"
    />
  </UFormField>
</template>
