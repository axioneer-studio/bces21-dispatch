export type ToastType = 'info' | 'success' | 'error' | 'warning'

export interface ToastInput {
  type?: ToastType
  message: string
  title?: string
  duration?: number
}

export interface Toast extends Required<Omit<ToastInput, 'title'>> {
  id: number
  title: string | null
  createdAt: number
  paused: boolean
}
