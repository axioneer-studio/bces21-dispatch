import type { ToastInput } from '~/composables/useToastStore'

export function useToast() {
  const store = useToastStore()

  function push(input: ToastInput) {
    return store.push(input)
  }

  return {
    push,
    info: (message: string, opts: Partial<ToastInput> = {}) =>
      push({ ...opts, type: 'info', message }),
    success: (message: string, opts: Partial<ToastInput> = {}) =>
      push({ ...opts, type: 'success', message }),
    error: (message: string, opts: Partial<ToastInput> = {}) =>
      push({ ...opts, type: 'error', message }),
    warning: (message: string, opts: Partial<ToastInput> = {}) =>
      push({ ...opts, type: 'warning', message }),
    dismiss: store.dismiss,
    clear: store.clear
  }
}