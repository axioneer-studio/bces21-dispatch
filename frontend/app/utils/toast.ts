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
}

export const ERROR_MESSAGES: Record<string, string> = {
  discord_misconfigured: 'Identifiants Discord non configurés côté serveur.',
  invalid_state: 'Session OAuth expirée ou invalide.',
  discord_failed: 'Connexion Discord refusée.',
  discord_profile_unavailable: 'Profil Discord indisponible.',
  unknown_account: 'Aucun compte n’est associé à ce profil Discord.',
  missing_code: 'Code OAuth manquant.',
  not_authenticated: 'Tu dois être connecté pour accéder à cette page.',
  invalid_token: 'Session invalide.',
  expired_token: 'Session expirée.'
}

export function useErrorMessage(code: string | null | undefined): string | null {
  if (!code) return null
  return ERROR_MESSAGES[code] ?? code
}