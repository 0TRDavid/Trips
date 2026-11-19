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

## 2026-11-19 — Étape 2 (import Nextcloud)

- **WebDAV avec `requests` + `xml.etree`** (PROPFIND Depth 1, parcours récursif). Deux opérations seulement, faciles à relire et à tester. *Écartés :* webdavclient3 (abandonné), nc-py-api (bien trop large).
- **Originaux lus en mémoire uniquement** (`BytesIO`), jamais écrits sur disque. Pillow lit l'en-tête sans décoder l'image.
- **CR2 (RAW Canon) importés comme des photos**, en lisant seulement les 256 premiers Ko (requête `Range`) : les EXIF sont en tête, inutile de télécharger 24 Mo. Si la date manque dans l'en-tête, on télécharge le fichier entier. Le rendu web (étape 3) viendra du JPEG que le CR2 embarque. *Écarté :* ignorer les CR2 (64 photos sur 98 dans la sélection Japon).
- **Date de prise** : `DateTimeOriginal` + `OffsetTimeOriginal` quand il existe (iPhone) → UTC exact. Sans décalage, l'heure est lue dans l'**horloge de l'appareil** si elle est connue, sinon dans le fuseau du voyage.
- **Horloges par appareil** (`--horloge "Canon EOS 100D=UTC"`, mémorisées dans `Voyage.horloges_appareils`) : le Canon n'écrit pas de décalage, et son horloge était en UTC (déduit en comparant ses séquences avec celles de l'iPhone). Changer l'horloge d'un appareil relit automatiquement ses photos. *Écarté :* tout lire dans le fuseau du voyage (Canon décalé de 9 h, photos sur le mauvais jour).
- **Images sans date EXIF** : date de modification Nextcloud, importées avec `visible=False` et listées dans le rapport, pour que le compte corresponde.
- **Relance** : clé unique `chemin_nextcloud` ; etag inchangé → ni téléchargement ni écriture ; etag modifié → métadonnées techniques relues, saisie de l'auteur (légende, favori, ordre, visibilité, récits, titres) conservée. Une transaction par photo : un import interrompu reprend là où il s'est arrêté. Les fichiers disparus de Nextcloud sont signalés, jamais supprimés.
- **`Voyage.dossier_nextcloud`** ajouté au modèle pour retrouver le voyage à la relance. **`Rendu`** reporté à l'étape 3.
- **Orientation** : rotation qu'il reste à appliquer à l'image *décodée*. Pour un HEIC, libheif applique déjà la rotation et pillow-heif remet l'EXIF à 1 ; pour JPEG et CR2, valeur EXIF d'origine.
- **Fichiers retenus** : `.heic .heif .jpg .jpeg .cr2` ; vidéos et autres fichiers ignorés et comptés (les vidéos arrivent en v2).
