import { ref, type Ref } from "vue";
import { useGlobalLoading } from "./useGlobalLoading";

/**
 * Récupère des données avec un indicateur de chargement global affiché
 * automatiquement pendant la requête.
 *
 * start() est appelé de manière synchrone avant toute attente, donc le loader
 * s'affiche avant que le template de la page ne soit rendu : aucun flash de
 * la page derrière n'est visible pendant le chargement.
 *
 * @param key - Clé unique (uniquement pour le débogage)
 * @param handler - Fonction asynchrone qui récupère les données (ex: $fetch)
 * @returns Objet avec la propriété `data` (ref) contenant le résultat
 */
export async function useAsyncDataWithLoading<T>(
  key: string,
  handler: () => Promise<T>,
): Promise<{ data: Ref<T | null> }> {
  const { start, stop } = useGlobalLoading();
  const data = ref<T | null>(null);

  start();
  try {
    const result = await handler();
    data.value = result;
    // Délai minimum d'affichage pour que le loader soit visible,
    // même si les données arrivent immédiatement (cache).
    await new Promise((resolve) => setTimeout(resolve, 300));
    return { data: data as Ref<T | null> };
  } finally {
    stop();
  }
}
