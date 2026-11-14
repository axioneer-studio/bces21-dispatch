const protectedPages: Record<string, string> = {
  '/dispatch': 'dispatch',
  '/hopital': 'hospital',
  '/stock': 'stock',
  '/agenda': 'agenda',
  '/ressources-humaines': 'human-resources',
  '/direction': 'direction',
  '/administration': 'administration'
}

/**
 * Pages ouvertes à tout compte validé, même sans rôle : elles n'ont pas de case à
 * cocher dans les rôles. Un compte en attente ou désactivé reçoit un 403 sur
 * /api/me et repart vers la connexion.
 */
const publicPages = new Set(['dispatch', 'hospital', 'agenda', 'stock'])

export default defineNuxtRouteMiddleware(async (to) => {
  const page = protectedPages[to.path]
  if (!page) return

  const headers = import.meta.server ? useRequestHeaders(['cookie']) : undefined
  let user: { is_super_admin: boolean; page_access: string[] } | null
  try {
    user = await $fetch<{ is_super_admin: boolean; page_access: string[] }>(
      '/api/me',
      { credentials: 'include', headers }
    )
  } catch {
    return navigateTo('/')
  }
  if (!user) return navigateTo('/')

  if (publicPages.has(page)) return
  if (user.is_super_admin || user.page_access.includes(page)) return

  return navigateTo('/dispatch')
})
