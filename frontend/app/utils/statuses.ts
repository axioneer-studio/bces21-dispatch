/**
 * Statut d'intervention, géré dans Administration et reçu avec le snapshot du
 * Dispatch. `key` est la valeur enregistrée sur l'intervention.
 */
export interface InterventionStatus {
  id: number;
  key: string;
  label: string;
  emoji: string;
  /** Couleur « #rrggbb » de l'intervention, ou aucune. */
  color: string | null;
  /** Statut « Primo Inter » : l'intervention est liée à la page Crise. */
  is_primo: boolean;
  /** Statut (Patrouille, Inter…) ou lieu (BCES, Zombie…) : les statuts passent en premier. */
  kind: InterventionStatusKind;
}

export type InterventionStatusKind = "status" | "place";

export const STATUS_KINDS: { value: InterventionStatusKind; label: string }[] =
  [
    { value: "status", label: "Statuts" },
    { value: "place", label: "Lieux" },
  ];

export function findStatus(
  statuses: InterventionStatus[],
  key: string | null | undefined,
): InterventionStatus | null {
  if (!key) return null;
  return statuses.find((status) => status.key === key) ?? null;
}
