// Hooks de récupération des données, avec cache (TanStack Query).
//
// Pourquoi un cache : en revenant d'un jour vers le voyage (bouton retour),
// les données sont déjà là, la page s'affiche instantanément, sans
// squelette ni saut. Indispensable aussi pour les transitions de l'étape 6.

import { QueryClient, useQuery } from "@tanstack/react-query";
import { fetchJson, Introuvable } from "./client";
import type { JourDetail, VoyageDetail, VoyageResume } from "./types";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Les récits changent rarement : 5 min sans redemander au serveur.
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
      // Inutile de réessayer une ressource qui n'existe pas.
      retry: (echecs, erreur) => !(erreur instanceof Introuvable) && echecs < 2,
    },
  },
});

export const cles = {
  voyages: ["voyages"] as const,
  voyage: (slug: string) => ["voyage", slug] as const,
  jour: (slug: string, date: string) => ["jour", slug, date] as const,
};

export function useVoyages() {
  return useQuery({
    queryKey: cles.voyages,
    queryFn: ({ signal }) => fetchJson<VoyageResume[]>("/api/voyages/", signal),
  });
}

export function useVoyage(slug: string) {
  return useQuery({
    queryKey: cles.voyage(slug),
    queryFn: ({ signal }) =>
      fetchJson<VoyageDetail>(`/api/voyages/${encodeURIComponent(slug)}/`, signal),
  });
}

function optionsJour(slug: string, date: string) {
  return {
    queryKey: cles.jour(slug, date),
    queryFn: ({ signal }: { signal: AbortSignal }) =>
      fetchJson<JourDetail>(
        `/api/voyages/${encodeURIComponent(slug)}/jours/${encodeURIComponent(date)}/`,
        signal,
      ),
  };
}

export function useJour(slug: string, date: string) {
  return useQuery(optionsJour(slug, date));
}

/** Précharge un jour (survol d'un lien) : la page s'ouvre sans attendre. */
export function prechargerJour(slug: string, date: string) {
  return queryClient.prefetchQuery(optionsJour(slug, date));
}
