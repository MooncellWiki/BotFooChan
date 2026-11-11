<script setup lang="ts">
defineProps<{ title: string, description?: string }>()
</script>

<template>
  <UDashboardPanel :id="title">
    <template #header>
      <UDashboardNavbar :title="title">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <slot name="actions" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p v-if="description" class="-mt-2 text-sm text-muted">
        {{ description }}
      </p>
      <slot />
    </template>
  </UDashboardPanel>
</template>
