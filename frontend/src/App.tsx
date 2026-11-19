import { useEffect, useState } from "react";
import { fetchHealth } from "./api";

// Les trois états possibles de l'appel à /api/health.
type ApiState =
  | { kind: "loading" }
  | { kind: "ok" }
  | { kind: "error"; detail: string };

export default function App() {
  const [api, setApi] = useState<ApiState>({ kind: "loading" });

  // Exécuté une fois à l'affichage du composant ([] = pas de dépendances).
  useEffect(() => {
    const controller = new AbortController();

    fetchHealth(controller.signal)
      .then((health) =>
        setApi(
          health.status === "ok"
            ? { kind: "ok" }
            : { kind: "error", detail: health.database },
        ),
      )
      .catch((err: unknown) => {
        if (controller.signal.aborted) return; // annulation volontaire
        setApi({ kind: "error", detail: String(err) });
      });

    // Nettoyage : annule la requête si le composant disparaît
    // (StrictMode monte deux fois en dev pour vérifier ce point).
    return () => controller.abort();
  }, []);

  return (
    <main className="home">
      <h1>Carnet de voyages</h1>
      <p className={`api-status api-status--${api.kind}`}>
        {api.kind === "loading" && "Connexion à l'API…"}
        {api.kind === "ok" && "API OK"}
        {api.kind === "error" && `API injoignable (${api.detail})`}
      </p>
    </main>
  );
}
