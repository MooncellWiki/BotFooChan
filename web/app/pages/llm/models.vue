<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { useQuery } from '@pinia/colada'
import type { ModelOut, ProviderIn, ProviderOut } from '~/client'
import { deleteModel, deleteProvider, listRemoteModels, putModel, putProvider, testModel } from '~/client'
import { getLlmQuery } from '~/client/@pinia/colada.gen'

const { data, error, isLoading, refetch } = useQuery(getLlmQuery())
const { run, pending } = useAction()
const toast = useToast()

const AUTO = '__auto__'
const apiTypeItems = computed(() => [
  { label: '自动', value: AUTO },
  ...(data.value?.api_types ?? []).map(v => ({ label: v, value: v })),
])
const visionItems = [
  { label: '自动判断', value: AUTO },
  { label: '支持看图', value: 'true' },
  { label: '不支持', value: 'false' },
]
const fromVision = (v: boolean | null | undefined) => (v === null || v === undefined ? AUTO : String(v))
const toVision = (v: string) => (v === AUTO ? null : v === 'true')
type ApiType = NonNullable<ProviderIn['api_type']>
const toApiType = (v: string) => (v === AUTO ? null : (v as ApiType))

// ---------- 服务商 ----------
const providerOpen = ref(false)
const providerEditing = ref(false)
const providerMasked = ref<string | null>(null)
const providerForm = ref({ name: '', base_url: '', api_key: '', api_type: AUTO, vision: AUTO, proxy: '' })

function openProvider(provider?: ProviderOut) {
  providerEditing.value = Boolean(provider)
  providerMasked.value = provider?.api_key ?? null
  providerForm.value = {
    name: provider?.name ?? '',
    base_url: provider?.base_url ?? '',
    api_key: '',
    api_type: provider?.api_type ?? AUTO,
    vision: fromVision(provider?.vision),
    proxy: provider?.proxy ?? '',
  }
  providerOpen.value = true
}

async function saveProvider() {
  const result = await run(() => putProvider({
    path: { name: providerForm.value.name.trim() },
    body: {
      base_url: providerForm.value.base_url.trim(),
      api_key: providerForm.value.api_key || providerMasked.value,
      api_type: toApiType(providerForm.value.api_type),
      vision: toVision(providerForm.value.vision),
      proxy: providerForm.value.proxy.trim() || null,
    },
    throwOnError: true,
  }), '服务商已保存')
  if (result) {
    providerOpen.value = false
    await refetch()
  }
}

async function removeProvider(name: string) {
  if (await run(() => deleteProvider({ path: { name }, throwOnError: true }), `已删除服务商 ${name}`)) await refetch()
}

// ---------- 模型 ----------
const modelOpen = ref(false)
const modelEditing = ref(false)
const modelForm = ref({ alias: '', provider: '', name: '', api_type: AUTO, vision: AUTO })
const remoteModels = ref<string[]>([])
const fetchingRemote = ref(false)

function openModel(model?: ModelOut) {
  modelEditing.value = Boolean(model)
  remoteModels.value = []
  modelForm.value = {
    alias: model?.alias ?? '',
    provider: model?.provider ?? data.value?.providers[0]?.name ?? '',
    name: model?.name ?? '',
    api_type: model?.api_type ?? AUTO,
    vision: fromVision(model?.vision),
  }
  modelOpen.value = true
}

async function fetchRemote() {
  fetchingRemote.value = true
  const result = await run(() => listRemoteModels({ path: { name: modelForm.value.provider }, throwOnError: true }))
  fetchingRemote.value = false
  if (!result) return
  if (result.data.error) toast.add({ title: '拉取失败', description: result.data.error, color: 'error' })
  remoteModels.value = result.data.models ?? []
}

async function saveModel() {
  const result = await run(() => putModel({
    path: { alias: modelForm.value.alias.trim() },
    body: {
      provider: modelForm.value.provider,
      name: modelForm.value.name.trim(),
      api_type: toApiType(modelForm.value.api_type),
      vision: toVision(modelForm.value.vision),
    },
    throwOnError: true,
  }), '模型已保存')
  if (result) {
    modelOpen.value = false
    await refetch()
  }
}

async function removeModel(alias: string) {
  if (await run(() => deleteModel({ path: { alias }, throwOnError: true }), `已删除模型 ${alias}`)) await refetch()
}

const testing = ref<string | null>(null)
async function test(alias: string) {
  testing.value = alias
  const result = await run(() => testModel({ path: { alias }, throwOnError: true }))
  testing.value = null
  if (!result) return
  const r = result.data
  toast.add(r.ok
    ? { title: `${alias} 正常（${r.latency_ms} ms）`, description: r.output, color: 'success', icon: 'i-lucide-circle-check' }
    : { title: `${alias} 调用失败`, description: r.error, color: 'error', icon: 'i-lucide-circle-alert', duration: 10000 })
}

const providerColumns: TableColumn<ProviderOut>[] = [
  { accessorKey: 'name', header: '名称' },
  { accessorKey: 'base_url', header: '地址' },
  { accessorKey: 'api_key', header: 'API Key' },
  { accessorKey: 'api_type', header: '协议' },
  { accessorKey: 'models', header: '模型' },
  { id: 'actions', header: '' },
]
const modelColumns: TableColumn<ModelOut>[] = [
  { accessorKey: 'alias', header: '别名' },
  { accessorKey: 'provider', header: '服务商' },
  { accessorKey: 'name', header: '模型名' },
  { accessorKey: 'resolved_api_type', header: '协议' },
  { accessorKey: 'supports_vision', header: '看图' },
  { accessorKey: 'routes', header: '在用的功能' },
  { id: 'actions', header: '' },
]
</script>

<template>
  <AppPage title="模型" description="服务商（地址和 API Key）与模型别名。各功能具体用哪个模型在「模型路由」里选。">
    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-64" />

    <template v-if="data">
      <UCard :ui="{ body: 'p-0 sm:p-0' }">
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="font-semibold">
              服务商
            </h2>
            <UButton label="添加服务商" icon="i-lucide-plus" size="sm" @click="openProvider()" />
          </div>
        </template>
        <UTable :data="data.providers" :columns="providerColumns" empty="还没有服务商">
          <template #name-cell="{ row }">
            <span class="font-medium">{{ row.original.name }}</span>
          </template>
          <template #base_url-cell="{ row }">
            <code class="text-xs">{{ row.original.base_url }}</code>
            <UBadge v-if="row.original.proxy" label="代理" color="neutral" variant="subtle" size="sm" class="ms-1" />
          </template>
          <template #api_key-cell="{ row }">
            <UBadge v-if="row.original.api_key" label="已设置" color="success" variant="subtle" />
            <UBadge v-else label="未设置" color="error" variant="subtle" />
          </template>
          <template #api_type-cell="{ row }">
            {{ row.original.api_type ?? '自动' }}
          </template>
          <template #models-cell="{ row }">
            <span class="text-muted">{{ row.original.models.length }} 个</span>
          </template>
          <template #actions-cell="{ row }">
            <div class="flex justify-end gap-1">
              <UButton icon="i-lucide-pencil" color="neutral" variant="ghost" size="sm" aria-label="编辑" @click="openProvider(row.original)" />
              <ConfirmButton :message="`删除服务商 ${row.original.name}？`" @confirm="removeProvider(row.original.name)" />
            </div>
          </template>
        </UTable>
      </UCard>

      <UCard :ui="{ body: 'p-0 sm:p-0' }">
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="font-semibold">
              模型
            </h2>
            <UButton label="添加模型" icon="i-lucide-plus" size="sm" :disabled="!data.providers.length" @click="openModel()" />
          </div>
        </template>
        <UTable :data="data.models" :columns="modelColumns" empty="还没有模型">
          <template #alias-cell="{ row }">
            <span class="font-medium">{{ row.original.alias }}</span>
          </template>
          <template #name-cell="{ row }">
            <code class="text-xs">{{ row.original.name }}</code>
          </template>
          <template #resolved_api_type-cell="{ row }">
            {{ row.original.resolved_api_type ?? '—' }}
            <span v-if="!row.original.api_type" class="text-xs text-dimmed">（自动）</span>
          </template>
          <template #supports_vision-cell="{ row }">
            <UIcon v-if="row.original.supports_vision" name="i-lucide-check" class="text-success" />
            <span v-else class="text-dimmed">—</span>
          </template>
          <template #routes-cell="{ row }">
            <div class="flex flex-wrap gap-1">
              <UBadge v-for="r in row.original.routes" :key="r" :label="r" color="neutral" variant="subtle" size="sm" />
            </div>
          </template>
          <template #actions-cell="{ row }">
            <div class="flex justify-end gap-1">
              <UButton icon="i-lucide-play" color="neutral" variant="ghost" size="sm" aria-label="测试" :loading="testing === row.original.alias" @click="test(row.original.alias)" />
              <UButton icon="i-lucide-pencil" color="neutral" variant="ghost" size="sm" aria-label="编辑" @click="openModel(row.original)" />
              <ConfirmButton :message="`删除模型 ${row.original.alias}？`" @confirm="removeModel(row.original.alias)" />
            </div>
          </template>
        </UTable>
      </UCard>
    </template>

    <UModal v-model:open="providerOpen" :title="providerEditing ? `编辑服务商 ${providerForm.name}` : '添加服务商'">
      <template #body>
        <div class="grid gap-4">
          <UFormField v-if="!providerEditing" label="名称" required>
            <UInput v-model="providerForm.name" placeholder="如 deepseek" class="w-full" />
          </UFormField>
          <UFormField label="地址" description="OpenAI 兼容接口地址；Anthropic 协议填服务商的 Anthropic 地址" required>
            <UInput v-model="providerForm.base_url" placeholder="https://api.deepseek.com" class="w-full" />
          </UFormField>
          <UFormField label="API Key">
            <UInput
              v-model="providerForm.api_key"
              type="password"
              autocomplete="new-password"
              :placeholder="providerMasked ? '已设置，留空表示不改' : 'sk-…'"
              class="w-full"
            />
          </UFormField>
          <div class="grid gap-4 sm:grid-cols-2">
            <UFormField label="协议">
              <USelect v-model="providerForm.api_type" :items="apiTypeItems" class="w-full" />
            </UFormField>
            <UFormField label="看图">
              <USelect v-model="providerForm.vision" :items="visionItems" class="w-full" />
            </UFormField>
          </div>
          <UFormField label="代理">
            <UInput v-model="providerForm.proxy" placeholder="http://127.0.0.1:7890" class="w-full" />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton label="取消" color="neutral" variant="ghost" @click="providerOpen = false" />
          <UButton label="保存" :loading="pending" :disabled="!providerForm.name || !providerForm.base_url" @click="saveProvider" />
        </div>
      </template>
    </UModal>

    <UModal v-model:open="modelOpen" :title="modelEditing ? `编辑模型 ${modelForm.alias}` : '添加模型'">
      <template #body>
        <div class="grid gap-4">
          <UFormField v-if="!modelEditing" label="别名" description="各功能按别名引用模型" required>
            <UInput v-model="modelForm.alias" placeholder="如 deepseek-flash" class="w-full" />
          </UFormField>
          <UFormField label="服务商" required>
            <USelect v-model="modelForm.provider" :items="(data?.providers ?? []).map(p => p.name)" class="w-full" />
          </UFormField>
          <UFormField label="模型名" required>
            <div class="flex gap-2">
              <USelectMenu
                v-if="remoteModels.length"
                v-model="modelForm.name"
                :items="remoteModels"
                create-item
                class="w-full"
                @create="(item: string) => (modelForm.name = item)"
              />
              <UInput v-else v-model="modelForm.name" placeholder="服务商那边的模型名" class="w-full" />
              <UButton label="拉取列表" icon="i-lucide-download" color="neutral" variant="outline" :loading="fetchingRemote" :disabled="!modelForm.provider" @click="fetchRemote" />
            </div>
          </UFormField>
          <div class="grid gap-4 sm:grid-cols-2">
            <UFormField label="协议" description="覆写服务商的设置">
              <USelect v-model="modelForm.api_type" :items="apiTypeItems" class="w-full" />
            </UFormField>
            <UFormField label="看图" description="覆写服务商的设置">
              <USelect v-model="modelForm.vision" :items="visionItems" class="w-full" />
            </UFormField>
          </div>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton label="取消" color="neutral" variant="ghost" @click="modelOpen = false" />
          <UButton label="保存" :loading="pending" :disabled="!modelForm.alias || !modelForm.provider || !modelForm.name" @click="saveModel" />
        </div>
      </template>
    </UModal>
  </AppPage>
</template>
