const protectedPages: Record<string, string> = {
  '/dashboard': 'dashboard',
  '/dispatch': 'dispatch',
  '/agenda': 'agenda',
  '/ressources-humaines': 'human-resources',
  '/direction': 'direction',
  '/administration': 'administration'
}

const pageRoutes: Record<string, string> = {
  dashboard: '/dashboard',
  dispatch: '/dispatch',
  agenda: '/agenda',
  'human-resources': '/ressources-humaines',
  direction: '/direction',
  administration: '/administration'
}

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

  if (page === 'agenda') return
  if (user.is_super_admin || user.page_access.includes(page)) return

  const firstAllowedPage = user.page_access.find((key) => key in pageRoutes)
  return navigateTo(firstAllowedPage ? pageRoutes[firstAllowedPage] : '/acces-refuse')
})
