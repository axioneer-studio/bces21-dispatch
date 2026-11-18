/**
 * Groupe d'appartenance, géré dans Administration et proposé dans la Crise et
 * la Morgue. Les fiches gardent leur appartenance en texte libre.
 */
export interface AffiliationGroup {
  id: number
  name: string
  /** Couleur « #rrggbb » de l'appartenance, ou aucune. */
  color: string | null
}

/** Couleur du groupe qui porte ce nom (sans tenir compte de la casse), ou aucune. */
export function groupColor(groups: AffiliationGroup[], name: string | null | undefined): string | null {
  const key = name?.trim().toLocaleLowerCase('fr')
  if (!key) return null
  return groups.find((group) => group.name.toLocaleLowerCase('fr') === key)?.color ?? null
}
