<script setup lang="ts">
import { useQuery } from '@pinia/colada'
import type { RelaunchResult } from '~/client'
import { relaunchTorappu } from '~/client'
import { listTorappuVersionsQuery } from '~/client/@pinia/colada.gen'

const { data, error, isLoading } = useQuery(listTorappuVersionsQuery({ query: { limit: 50 } }))
const { run, pending } = useAction()

const target = ref<number>()
const prev = ref<number>()
const include = ref('')
const exclude = ref('')
const result = ref<RelaunchResult | null>(null)

const items = computed(() => (data.value ?? []).map(v => ({ label: `${v.res_version}（${v.client_version}）`, value: v.id })))
watch(data, (versions) => {
  if (!versions?.length || target.value !== undefined) return
  target.value = versions[0]!.id
  prev.value = versions[1]?.id
}, { immediate: true })
watch(target, (id) => {
  // 换了目标版本就默认对比它的上一版
  const versions = data.value ?? []
  const index = versions.findIndex(v => v.id === id)
  if (index >= 0) prev.value = versions[index + 1]?.id
})

async function launch() {
  if (target.value === undefined || prev.value === undefined) return
  const response = await run(() => relaunchTorappu({
    body: { version_id: target.value!, prev_version_id: prev.value!, include: include.value.trim() || null, exclude: exclude.value.trim() || null },
    throwOnError: true,
  }), '已发起重跑')
  if (response) result.value = response.data
}
</script>

<template>
  <AppPage title="Torappu 重跑" description="对两个版本重新跑一遍解包（等同聊天里的 /重跑）。">
    <UAlert v-if="error" color="error" variant="subtle" title="加载版本列表失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-48" />
    <UCard v-if="data">
      <div class="grid gap-4 md:grid-cols-2">
        <UFormField label="目标版本" required>
          <USelect v-model="target" :items="items" class="w-full" />
        </UFormField>
        <UFormField label="上一版本" description="和它比较差异" required>
          <USelect v-model="prev" :items="items" class="w-full" />
        </UFormField>
        <UFormField label="只处理这些路径" description="可选，--include">
          <UInput v-model="include" class="w-full" />
        </UFormField>
        <UFormField label="跳过这些路径" description="可选，--exclude">
          <UInput v-model="exclude" class="w-full" />
        </UFormField>
      </div>
      <template #footer>
        <div class="flex justify-end">
          <ConfirmButton
            label="发起重跑"
            icon="i-lucide-rocket"
            confirm-label="发起"
            :loading="pending"
            :message="`对 ${items.find(i => i.value === prev)?.label} → ${items.find(i => i.value === target)?.label} 发起重跑？`"
            @confirm="launch"
          />
        </div>
      </template>
    </UCard>
    <UCard v-if="result">
      <p class="text-sm">
        容器 <code>{{ result.container_name }}</code> · 状态 {{ result.status }}
      </p>
    </UCard>
  </AppPage>
</template>
