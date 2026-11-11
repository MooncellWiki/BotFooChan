<script setup lang="ts">
import { useQuery } from '@pinia/colada'
import { putSettings } from '~/client'
import { getSettingsQuery } from '~/client/@pinia/colada.gen'
import type { JsonSchema } from '~/utils/schema'

const route = useRoute()
const key = computed(() => String(route.params.key))
const toast = useToast()

const { data, error, isLoading, refetch } = useQuery(() => getSettingsQuery({ path: { key: key.value } }))

const draft = ref<Record<string, unknown>>({})
const jsonText = ref('')
const errors = ref<Record<string, string>>({})
const saving = ref(false)

function reset() {
  if (!data.value) return
  draft.value = structuredClone(toRaw(data.value.value))
  jsonText.value = JSON.stringify(data.value.value, null, 2)
  errors.value = {}
}
watch(data, reset, { immediate: true })

const dirty = computed(() => data.value && JSON.stringify(draft.value) !== JSON.stringify(data.value.value))
const schema = computed(() => data.value?.json_schema as JsonSchema | undefined)

async function save(body: Record<string, unknown>) {
  saving.value = true
  const before = data.value?.value ?? {}
  const { error: saveError } = await putSettings({ path: { key: key.value }, body })
  saving.value = false
  if (saveError) {
    errors.value = fieldErrors(saveError)
    toast.add({ title: '保存失败', description: errorMessage(saveError), color: 'error', icon: 'i-lucide-circle-alert' })
    return
  }
  const restart = (data.value?.restart_fields ?? []).filter(f => JSON.stringify(before[f]) !== JSON.stringify(body[f]))
  toast.add({
    title: '已保存，立即生效',
    description: restart.length ? `${restart.join('、')} 要重启后才生效` : undefined,
    color: restart.length ? 'warning' : 'success',
    icon: 'i-lucide-circle-check',
  })
  await refetch()
}

function saveJson() {
  try {
    const body = JSON.parse(jsonText.value)
    if (!isPlainObject(body)) throw new Error('要是一个 JSON 对象')
    save(body)
  }
  catch (e) {
    toast.add({ title: 'JSON 有误', description: errorMessage(e), color: 'error' })
  }
}

const tabs = [
  { label: '表单', slot: 'form' as const, icon: 'i-lucide-list' },
  { label: 'JSON', slot: 'json' as const, icon: 'i-lucide-braces' },
]
</script>

<template>
  <AppPage :title="data ? `设置 · ${data.title}` : '设置'" :description="data?.description">
    <template #actions>
      <UButton label="返回" icon="i-lucide-arrow-left" color="neutral" variant="ghost" to="/settings" />
    </template>

    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-96" />

    <template v-if="data && schema">
      <UAlert
        v-if="!data.editable"
        color="warning"
        variant="subtle"
        icon="i-lucide-triangle-alert"
        title="只读"
        description="配置没有从数据库加载（没配 WEBUI__SECRET_KEY？），现在读的是 .env，改不了。"
      />
      <p class="text-xs text-muted">
        <span class="font-mono">{{ data.key }}</span>
        · 来源：{{ data.source === 'database' ? '数据库' : '.env' }}
        <template v-if="data.updated_at">
          · 最后由 {{ data.updated_by }} 修改于 {{ formatDateTime(data.updated_at) }}
        </template>
      </p>

      <UTabs :items="tabs" variant="link" class="w-full">
        <template #form>
          <UCard class="mt-2">
            <SchemaForm v-model="draft" :schema="schema" :errors="errors" />
            <template #footer>
              <div class="flex justify-end gap-2">
                <UButton label="还原" color="neutral" variant="ghost" :disabled="!dirty" @click="reset" />
                <UButton label="保存" icon="i-lucide-save" :loading="saving" :disabled="!dirty || !data.editable" @click="save(draft)" />
              </div>
            </template>
          </UCard>
        </template>
        <template #json>
          <UCard class="mt-2">
            <p class="mb-2 text-xs text-muted">
              整段 JSON。密钥是打码后的值，原样保留表示不改；要换就填新值。
            </p>
            <UTextarea v-model="jsonText" autoresize :rows="16" class="w-full font-mono text-xs" />
            <template #footer>
              <div class="flex justify-end gap-2">
                <UButton label="还原" color="neutral" variant="ghost" @click="reset" />
                <UButton label="保存 JSON" icon="i-lucide-save" :loading="saving" :disabled="!data.editable" @click="saveJson" />
              </div>
            </template>
          </UCard>
        </template>
      </UTabs>
    </template>
  </AppPage>
</template>
