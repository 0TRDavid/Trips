// Appels HTTP vers l'API. Les URL sont relatives (/api/...) : en dev, le proxy
// Vite les relaie au backend ; en prod, Nginx Proxy Manager fera de même.

/** La ressource n'existe pas (404) : la page affiche « introuvable ». */
export class Introuvable extends Error {
  constructor(url: string) {
    super(`Introuvable : ${url}`);
    this.name = "Introuvable";
  }
}

/** Toute autre erreur (réseau, 500…) : la page propose de réessayer. */
export class ErreurApi extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ErreurApi";
  }
}

export async function fetchJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (signal?.aborted) throw err;
    throw new ErreurApi("Le serveur ne répond pas.");
  }
  if (response.status === 404) throw new Introuvable(url);
  if (!response.ok) throw new ErreurApi(`Erreur du serveur (HTTP ${response.status}).`);
  // Garde-fou : si le proxy renvoie la page HTML de Vite au lieu du JSON.
  const type = response.headers.get("content-type") ?? "";
  if (!type.includes("json")) throw new ErreurApi("Réponse inattendue du serveur.");
  return (await response.json()) as T;
}
