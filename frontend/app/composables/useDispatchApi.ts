import type { DispatchRadio, DispatchSlot, DispatchState } from './useDispatchStore'

const config = () => useRuntimeConfig()

function base(): string {
  const apiBase = String(config().public.apiBase || '')
  return apiBase.replace(/\/$/, '')
}

async function req<T>(
  path: string,
  options: { method?: string; body?: unknown; credentials?: 'include' } = {}
): Promise<T> {
  const headers = import.meta.server ? useRequestHeaders(['cookie']) : undefined
  return await $fetch<T>(`${base()}${path}`, {
    method: options.method ?? 'GET',
    body: options.body as Record<string, unknown> | undefined,
    credentials: 'include',
    headers
  })
}

export async function fetchSnapshot() {
  return await req<{ slots: DispatchSlot[]; radios: DispatchRadio[]; state: DispatchState }>(
    '/api/dispatch/snapshot'
  )
}

export async function createSlot(kind: 'intervention' | 'consultation') {
  return await req<DispatchSlot>('/api/dispatch/slots', {
    method: 'POST',
    body: { kind }
  })
}

export async function updateSlot(
  id: number,
  patch: Partial<{
    title: string | null
    status: string | null
    zip_code: string | null
    location: string | null
    type_label: string | null
  }>
) {
  return await req<DispatchSlot>(`/api/dispatch/slots/${id}`, {
    method: 'PATCH',
    body: patch
  })
}

export async function deleteSlot(id: number) {
  return await req<{ message: string }>(`/api/dispatch/slots/${id}`, { method: 'DELETE' })
}

export async function assignUser(slotId: number, userId: number) {
  return await req<DispatchSlot>(`/api/dispatch/slots/${slotId}/assign`, {
    method: 'POST',
    body: { user_id: userId }
  })
}

export async function unassignUser(slotId: number, userId: number) {
  return await req<DispatchSlot>(`/api/dispatch/slots/${slotId}/assign/${userId}`, {
    method: 'DELETE'
  })
}

export async function updateRadio(
  id: number,
  patch: Partial<Pick<DispatchRadio, 'serial' | 'doctor_id' | 'is_on' | 'is_loading'>>
) {
  return await req<DispatchRadio>(`/api/dispatch/radios/${id}`, {
    method: 'PATCH',
    body: patch
  })
}

export async function updateState(
  patch: Partial<
    Pick<DispatchState, 'hospital_status' | 'lses_status' | 'safd_status' | 'radio_codes'>
  >
) {
  return await req<DispatchState>('/api/dispatch/state', {
    method: 'PATCH',
    body: patch
  })
}