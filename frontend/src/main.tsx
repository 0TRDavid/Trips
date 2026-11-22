import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import "@fontsource-variable/fraunces";
import "@fontsource-variable/inter";
import "./styles/global.css";
import { queryClient } from "./api/requetes";
import { publierDureesCss } from "./lib/mouvement";
import { router } from "./routes";

publierDureesCss();

// Dev seulement : la page /labo pilote le site affiché dans ses iframes.
if (import.meta.env.DEV) {
  (window as unknown as { __carnet: unknown }).__carnet = {
    naviguer: (vers: string, options?: Parameters<typeof router.navigate>[1]) => router.navigate(vers, options),
    retour: () => router.navigate(-1),
    montrer: (selecteur: string) => document.querySelector(selecteur)?.scrollIntoView({ block: "center" }),
    chemin: () => window.location.pathname,
    // Fait défiler la page jusqu'en bas à vitesse constante (px/s), comme un lecteur.
    defiler: (vitesse: number) =>
      new Promise<void>((fini) => {
        let avant = performance.now();
        const pas = (maintenant: number) => {
          const y = window.scrollY + (vitesse * (maintenant - avant)) / 1000;
          avant = maintenant;
          window.scrollTo(0, y);
          if (y >= document.documentElement.scrollHeight - window.innerHeight - 1) fini();
          else requestAnimationFrame(pas);
        };
        requestAnimationFrame(pas);
      }),
  };
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
