// Appels à l'API Django. Les URL sont relatives (/api/...) : en dev, le proxy
// Vite les relaie au backend ; en prod, Nginx Proxy Manager fera de même.

export type Health = {
  status: "ok" | "error";
  database: string;
};

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch("/api/health", { signal });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as Health;
}
