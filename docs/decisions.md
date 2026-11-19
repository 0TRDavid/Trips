# Journal des décisions

Format : date — choix — raison — alternatives écartées.

## 2026-11-19 — Étape 1 (squelette)

- **Proxy Vite `/api` → backend** plutôt que CORS. Le navigateur ne parle qu'à une seule origine, et le front n'a aucune URL d'API codée en dur. En prod, NPM fera le même routage. *Écarté :* django-cors-headers avec une URL d'API absolue.
- **Django 5.2 LTS** (support jusqu'en avril 2028). *Écarté :* Django 6.x, dont le support est plus court.
- **PostgreSQL 17** (`postgres:17-alpine`). Version récente et stable, image légère.
- **Settings lus via `os.environ`**, sans bibliothèque en plus. Peu de variables, et le code reste lisible. *Écarté :* django-environ et pydantic-settings, à reconsidérer si les réglages se multiplient.
- **Images Python 3.12 et Node 24 (LTS)** dans les conteneurs, quelles que soient les versions installées sur la VM.
- **Dépendances front reportées** : React Router, TanStack Query, Motion et GSAP arriveront aux étapes 5–6, quand elles serviront. Chaque diff reste ainsi lisible.
- **`node_modules` dans un volume anonyme** : ce sont ceux de l'image (Linux/Alpine) qui sont utilisés, jamais un dossier de l'hôte.
