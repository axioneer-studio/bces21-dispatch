import { $fetch } from 'ofetch'
import type { DispatchRadio, DispatchSlot, DispatchSnapshot, DispatchState, FleetEntry } from './useDispatchStore'

const config = () => useRuntimeConfig()

function base(): string {
  const apiBase = String(config().public.apiBase || '')
  return apiBase.replace(/\/$/, '')
}

async function req<T>(
  path: string,
  options: {
    method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
    body?: Record<string, unknown>
    credentials?: 'include'
  } = {}
): Promise<T> {
  const headers = import.meta.server ? useRequestHeaders(['cookie']) : undefined
  return await $fetch<T>(`${base()}${path}`, {
    method: options.method ?? 'GET',
    body: options.body,
    credentials: 'include',
    headers
  })
}

export async function fetchSnapshot() {
  return await req<DispatchSnapshot>('/api/dispatch/snapshot')
}

export async function resetAssignments(deleteInterventions: boolean) {
  return await req<DispatchSnapshot>(
    '/api/dispatch/assignments/reset',
    { method: 'POST', body: { delete_interventions: deleteInterventions } }
  )
}

export async function saveDispatchNote(content: string) {
  return await req<DispatchSnapshot>(
    '/api/dispatch/note',
    { method: 'PUT', body: { content } }
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

export async function assignUser(slotId: number, employeeId: number) {
  return await req<DispatchSlot>(`/api/dispatch/slots/${slotId}/assign`, {
    method: 'POST',
    body: { employee_id: employeeId }
  })
}

export async function unassignUser(slotId: number, employeeId: number) {
  return await req<DispatchSlot>(`/api/dispatch/slots/${slotId}/assign/${employeeId}`, {
    method: 'DELETE'
  })
}

export async function createFleetEntry() {
  return await req<FleetEntry>('/api/dispatch/fleet', { method: 'POST' })
}

export async function updateFleetEntry(
  id: number,
  patch: Partial<Pick<FleetEntry, 'vehicle_id' | 'location' | 'note'>>
) {
  return await req<FleetEntry>(`/api/dispatch/fleet/${id}`, {
    method: 'PATCH',
    body: patch
  })
}

export async function deleteFleetEntry(id: number) {
  return await req<{ message: string }>(`/api/dispatch/fleet/${id}`, { method: 'DELETE' })
}

export async function updateRadio(
  id: number,
  patch: Partial<Pick<DispatchRadio, 'employee_id' | 'is_on' | 'is_loading'>>
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