<script setup lang="ts">
import { useQuery } from '@pinia/colada'
import type { HistoryEntry, Prompt } from '~/client'
import { getSettingsHistory, putPrompt } from '~/client'
import { listPromptsQuery } from '~/client/@pinia/colada.gen'

const { data, error, isLoading, refetch } = useQuery(listPromptsQuery())
const { run } = useAction()

const drafts = reactive<Record<string, string>>({})
watch(data, (prompts) => {
  for (const p of prompts ?? []) drafts[p.id] = p.value
}, { immediate: true })

const saving = ref<string | null>(null)
async function save(prompt: Prompt) {
  saving.value = prompt.id
  const result = await run(() => putPrompt({
    path: { section: prompt.section, field: prompt.field },
    body: { value: drafts[prompt.id] ?? '' },
    throwOnError: true,
  }), '提示词已保存，立即生效')
  saving.value = null
  if (result) {
    await refetch()
    if (history[prompt.id]) await loadHistory(prompt)
  }
}

const history = reactive<Record<string, HistoryEntry[]>>({})
async function loadHistory(prompt: Prompt) {
  const result = await run(() => getSettingsHistory({
    path: { key: prompt.section },
    query: { path: prompt.field },
    throwOnError: true,
  }))
  if (result) history[prompt.id] = result.data
}

function versionOf(entry: HistoryEntry, field: string): string | undefined {
  const change = entry.changes[field]
  return change ? String(change[1] ?? '') : undefined
}
</script>

<template>
  <AppPage title="提示词" description="可以在后台改的提示词。每次修改都有记录，可以从历史里取回旧版本。">
    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-48" />
    <UEmpty v-if="data && !data.length" title="没有可编辑的提示词" icon="i-lucide-message-square-text" />

    <UCard v-for="prompt in data" :key="prompt.id">
      <template #header>
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 class="font-semibold">
              {{ prompt.section_title }}
            </h2>
            <p class="text-xs text-muted">
              <span class="font-mono">{{ prompt.id }}</span> · {{ prompt.description }}
            </p>
          </div>
          <span v-if="prompt.updated_at" class="text-xs text-dimmed">配置段最后修改于 {{ formatDateTime(prompt.updated_at) }}</span>
        </div>
      </template>

      <UTextarea v-model="drafts[prompt.id]" autoresize :rows="6" class="w-full" placeholder="（空）" />

      <div class="mt-3 flex justify-end gap-2">
        <UButton label="还原" color="neutral" variant="ghost" :disabled="drafts[prompt.id] === prompt.value" @click="drafts[prompt.id] = prompt.value" />
        <UButton label="保存" icon="i-lucide-save" :loading="saving === prompt.id" :disabled="drafts[prompt.id] === prompt.value" @click="save(prompt)" />
      </div>

      <UCollapsible class="mt-4" @update:open="(open: boolean) => open && !history[prompt.id] && loadHistory(prompt)">
        <UButton label="修改历史" icon="i-lucide-history" color="neutral" variant="ghost" size="sm" trailing-icon="i-lucide-chevron-down" />
        <template #content>
          <div class="mt-2 grid gap-2">
            <p v-if="history[prompt.id] && !history[prompt.id]!.length" class="text-sm text-muted">
              还没有修改记录
            </p>
            <div v-for="entry in history[prompt.id]" :key="entry.id" class="rounded-md border border-default p-3">
              <div class="flex items-center justify-between gap-2 text-xs text-muted">
                <span>{{ formatDateTime(entry.at) }} · {{ entry.actor }}</span>
                <UButton
                  label="用这一版"
                  icon="i-lucide-rotate-ccw"
                  size="xs"
                  color="neutral"
                  variant="outline"
                  @click="drafts[prompt.id] = versionOf(entry, prompt.field) ?? drafts[prompt.id] ?? ''"
                />
              </div>
              <pre class="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs">{{ versionOf(entry, prompt.field) || '（空）' }}</pre>
            </div>
          </div>
        </template>
      </UCollapsible>
    </UCard>
  </AppPage>
</template>
