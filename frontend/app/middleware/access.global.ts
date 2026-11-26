const protectedPages: Record<string, string> = {
  "/dispatch": "dispatch",
  "/crise": "crisis",
  "/hopital": "hospital",
  "/stock": "stock",
  "/agenda": "agenda",
  "/poles-specialites": "training",
  "/formation": "trainer",
  "/ressources-humaines": "human-resources",
  "/direction": "direction",
  "/administration": "administration",
};

/**
 * Pages ouvertes à tout compte validé, même sans rôle : elles n'ont pas de case à
 * cocher dans les rôles. Un compte en attente ou désactivé reçoit un 403 sur
 * /api/me et repart vers la connexion.
 */
const publicPages = new Set([
  "dispatch",
  "crisis",
  "hospital",
  "agenda",
  "stock",
  "training",
]);

/** Formation : réservée aux formateurs (droit donné par une formation de Pôles & Spé). */
const TRAINER_PERMISSION = "training.validate";

interface AccessUser {
  is_super_admin: boolean;
  page_access: string[];
  training_permissions: string[];
}

export default defineNuxtRouteMiddleware(async (to) => {
  const page = protectedPages[to.path];
  if (!page) return;

  const headers = import.meta.server
    ? useRequestHeaders(["cookie"])
    : undefined;
  let user: AccessUser | null;
  try {
    user = await $fetch<AccessUser>("/api/me", {
      credentials: "include",
      headers,
    });
  } catch {
    return navigateTo("/");
  }
  if (!user) return navigateTo("/");

  if (publicPages.has(page)) return;
  if (page === "trainer") {
    if (
      user.is_super_admin ||
      user.training_permissions.includes(TRAINER_PERMISSION)
    )
      return;
    return navigateTo("/dispatch");
  }
  if (user.is_super_admin || user.page_access.includes(page)) return;

  return navigateTo("/dispatch");
});
