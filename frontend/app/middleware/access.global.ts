const protectedPages: Record<string, string> = {
  '/dispatch': 'dispatch',
  '/hopital': 'hospital',
  '/stock': 'stock',
  '/agenda': 'agenda',
  '/ressources-humaines': 'human-resources',
  '/direction': 'direction',
  '/administration': 'administration'
}

const pageRoutes: Record<string, string> = {
  dispatch: '/dispatch',
  agenda: '/agenda',
  'human-resources': '/ressources-humaines',
  direction: '/direction',
  administration: '/administration'
}

/** Pages ouvertes à tout compte ayant un rôle, sans case à cocher dans les rôles. */
const publicPages = new Set(['agenda', 'hospital', 'stock'])

interface AccessUser {
  is_super_admin: boolean
  role_name: string | null
  page_access: string[]
}

export default defineNuxtRouteMiddleware(async (to) => {
  const page = protectedPages[to.path]
  if (!page) return

  const headers = import.meta.server ? useRequestHeaders(['cookie']) : undefined
  let user: AccessUser | null
  try {
    user = await $fetch<AccessUser>('/api/me', { credentials: 'include', headers })
  } catch {
    return navigateTo('/')
  }
  if (!user) return navigateTo('/')

  if (user.is_super_admin) return
  // Sans rôle, aucune page n'est accessible, pas même les pages ouvertes à tous.
  if (!user.role_name) return navigateTo('/acces-refuse')
  if (publicPages.has(page) || user.page_access.includes(page)) return

  const firstAllowedPage = user.page_access.find((key) => key in pageRoutes)
  return navigateTo(firstAllowedPage ? pageRoutes[firstAllowedPage] : '/agenda')
})
