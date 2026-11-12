<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { useQuery } from '@pinia/colada'
import type { BisonCookie, BisonSubscription } from '~/client'
import { addBisonSubscription, deleteBisonCookie, deleteBisonSubscription, updateBisonSubscription } from '~/client'
import { getBisonQuery } from '~/client/@pinia/colada.gen'

const { data, error, isLoading, refetch } = useQuery(getBisonQuery())
const { run, pending } = useAction()

const platformName = (name: string) => data.value?.platforms.find(p => p.name === name)?.display_name ?? name
const categoryNames = (platform: string, ids: number[]) => {
  const categories = data.value?.platforms.find(p => p.name === platform)?.categories ?? {}
  return ids.map(id => categories[id] ?? String(id))
}

// 按推送到的会话分组
const groups = computed(() => {
  const map = new Map<string, BisonSubscription[]>()
  for (const sub of data.value?.subscriptions ?? []) {
    map.set(sub.user_label, [...(map.get(sub.user_label) ?? []), sub])
  }
  return [...map.entries()]
})

// ---------- 添加 / 编辑 ----------
const open = ref(false)
const editing = ref<BisonSubscription | null>(null)
const form = ref({ user: '', platform: '', target: '', categories: [] as number[], tags: [] as string[] })

const userItems = computed(() => groups.value.map(([label]) => label))
const platformItems = computed(() => (data.value?.platforms ?? []).map(p => ({ label: `${p.display_name}（${p.name}）`, value: p.name })))
const currentPlatform = computed(() => data.value?.platforms.find(p => p.name === form.value.platform))
const categoryItems = computed(() => Object.entries(currentPlatform.value?.categories ?? {}).map(([id, name]) => ({ label: name, value: Number(id) })))

function openAdd(userLabel?: string) {
  editing.value = null
  form.value = { user: userLabel ?? userItems.value[0] ?? '', platform: data.value?.platforms[0]?.name ?? '', target: '', categories: [], tags: [] }
  open.value = true
}
function openEdit(sub: BisonSubscription) {
  editing.value = sub
  form.value = { user: sub.user_label, platform: sub.platform, target: sub.target, categories: [...sub.categories], tags: [...sub.tags] }
  open.value = true
}

async function save() {
  const sub = editing.value
  const result = sub
    ? await run(() => updateBisonSubscription({ path: { subscription_id: sub.id }, body: { categories: form.value.categories, tags: form.value.tags }, throwOnError: true }), '订阅已更新')
    : await run(() => addBisonSubscription({
        body: {
          user_target: groups.value.find(([label]) => label === form.value.user)?.[1][0]?.user_target ?? {},
          platform: form.value.platform,
          target: form.value.target.trim(),
          categories: form.value.categories,
          tags: form.value.tags,
        },
        throwOnError: true,
      }), '订阅已添加')
  if (result) {
    open.value = false
    await refetch()
  }
}

async function remove(sub: BisonSubscription) {
  if (await run(() => deleteBisonSubscription({ path: { subscription_id: sub.id }, throwOnError: true }), `已取消订阅 ${sub.target_name}`)) await refetch()
}
async function removeCookie(cookie: BisonCookie) {
  if (await run(() => deleteBisonCookie({ path: { cookie_id: cookie.id }, throwOnError: true }), `已删除 Cookie ${cookie.cookie_name}`)) await refetch()
}

const subColumns: TableColumn<BisonSubscription>[] = [
  { accessorKey: 'platform', header: '平台' },
  { accessorKey: 'target_name', header: '订阅对象' },
  { accessorKey: 'categories', header: '分类 / 标签' },
  { id: 'actions', header: '' },
]
const cookieColumns: TableColumn<BisonCookie>[] = [
  { accessorKey: 'cookie_name', header: '名称' },
  { accessorKey: 'site_name', header: '站点' },
  { accessorKey: 'status', header: '状态' },
  { accessorKey: 'targets', header: '关联' },
  { accessorKey: 'last_usage', header: '最后使用' },
  { id: 'actions', header: '' },
]
</script>

<template>
  <AppPage title="订阅推送" description="bison 的订阅：各平台动态推送到哪些会话。新会话要先在群里用 /添加订阅 订一次。">
    <template #actions>
      <UButton label="添加订阅" icon="i-lucide-plus" :disabled="!userItems.length" @click="openAdd()" />
    </template>

    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-64" />
    <UEmpty v-if="data && !data.subscriptions.length" icon="i-lucide-rss" title="还没有订阅" />

    <UCard v-for="[label, subs] in groups" :key="label" :ui="{ body: 'p-0 sm:p-0' }">
      <template #header>
        <div class="flex items-center justify-between gap-2">
          <h2 class="min-w-0 font-mono text-sm font-semibold [overflow-wrap:anywhere]">
            {{ label }}
          </h2>
          <UButton label="添加" icon="i-lucide-plus" size="xs" color="neutral" variant="ghost" class="shrink-0" @click="openAdd(label)" />
        </div>
      </template>
      <UTable :data="subs" :columns="subColumns" :ui="{ base: 'min-w-[40rem]' }">
        <template #platform-cell="{ row }">
          {{ platformName(row.original.platform) }}
        </template>
        <template #target_name-cell="{ row }">
          <p class="font-medium">
            {{ row.original.target_name }}
          </p>
          <p v-if="row.original.target" class="font-mono text-xs text-dimmed">
            {{ row.original.target }}
          </p>
        </template>
        <template #categories-cell="{ row }">
          <div class="flex max-w-md flex-wrap gap-1">
            <UBadge v-for="c in categoryNames(row.original.platform, row.original.categories)" :key="c" :label="c" color="neutral" variant="subtle" size="sm" />
            <UBadge v-for="t in row.original.tags" :key="t" :label="`#${t}`" color="primary" variant="subtle" size="sm" />
            <span v-if="!row.original.categories.length && !row.original.tags.length" class="text-xs text-dimmed">全部</span>
          </div>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end gap-1">
            <UButton icon="i-lucide-pencil" color="neutral" variant="ghost" size="sm" aria-label="编辑" @click="openEdit(row.original)" />
            <ConfirmButton :message="`取消 ${label} 对 ${row.original.target_name} 的订阅？`" @confirm="remove(row.original)" />
          </div>
        </template>
      </UTable>
    </UCard>

    <UCard v-if="data?.cookies.length" :ui="{ body: 'p-0 sm:p-0' }">
      <template #header>
        <h2 class="font-semibold">
          Cookie
        </h2>
        <p class="text-xs text-muted">
          内容不在这里显示；添加和关联仍在聊天里用 /添加Cookie、/关联Cookie。
        </p>
      </template>
      <UTable :data="data.cookies" :columns="cookieColumns">
        <template #cookie_name-cell="{ row }">
          {{ row.original.cookie_name }}
          <UBadge v-if="row.original.is_universal" label="通用" color="neutral" variant="subtle" size="sm" class="ms-1" />
          <UBadge v-if="row.original.is_anonymous" label="匿名" color="neutral" variant="subtle" size="sm" class="ms-1" />
        </template>
        <template #targets-cell="{ row }">
          <span class="text-xs">{{ row.original.targets.join('、') || '—' }}</span>
        </template>
        <template #last_usage-cell="{ row }">
          <span class="text-xs">{{ row.original.last_usage ? formatDateTime(row.original.last_usage) : '—' }}</span>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end">
            <ConfirmButton :message="`删除 Cookie ${row.original.cookie_name}？`" @confirm="removeCookie(row.original)" />
          </div>
        </template>
      </UTable>
    </UCard>

    <UModal v-model:open="open" :title="editing ? `编辑订阅 ${editing.target_name}` : '添加订阅'">
      <template #body>
        <div class="grid gap-4">
          <UFormField label="推送到" required>
            <USelect v-model="form.user" :items="userItems" :disabled="Boolean(editing)" class="w-full" />
          </UFormField>
          <UFormField label="平台" required>
            <USelect v-model="form.platform" :items="platformItems" :disabled="Boolean(editing)" class="w-full" />
          </UFormField>
          <UFormField v-if="currentPlatform?.has_target" label="订阅对象 id" description="如 B 站的 UID、微博的用户 id；保存时会去平台查名字" required>
            <UInput v-model="form.target" :disabled="Boolean(editing)" class="w-full" />
          </UFormField>
          <UFormField v-if="categoryItems.length" label="分类" description="不选表示全部">
            <USelectMenu v-model="form.categories" :items="categoryItems" value-key="value" multiple class="w-full" />
          </UFormField>
          <UFormField v-if="currentPlatform?.enable_tag" label="标签" description="只推送带这些标签的，不填表示全部">
            <UInputTags v-model="form.tags" class="w-full" />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton label="取消" color="neutral" variant="ghost" @click="open = false" />
          <UButton label="保存" :loading="pending" :disabled="!form.user || !form.platform || (!editing && currentPlatform?.has_target && !form.target.trim())" @click="save" />
        </div>
      </template>
    </UModal>
  </AppPage>
</template>
