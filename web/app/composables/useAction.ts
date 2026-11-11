/** 包一层接口操作：进行中状态、失败时弹出后端给的错误、成功时可选地提示一句 */
export function useAction() {
  const toast = useToast()
  const pending = ref(false)

  async function run<T>(fn: () => Promise<T>, success?: string): Promise<T | undefined> {
    pending.value = true
    try {
      const result = await fn()
      if (success) toast.add({ title: success, color: 'success', icon: 'i-lucide-circle-check' })
      return result
    }
    catch (error) {
      toast.add({ title: '操作失败', description: errorMessage(error), color: 'error', icon: 'i-lucide-circle-alert' })
      return undefined
    }
    finally {
      pending.value = false
    }
  }

  return { run, pending }
}
