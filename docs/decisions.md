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

## 2026-11-19 — Étape 3 (rendus)

- **WebP en trois tailles** (côté long 400 / 1280 / 2560 px, qualité 75 / 80 / 82), jamais agrandis. Japon : 98 photos → 294 fichiers, **69,5 Mo** (miniatures 2,2 Mo, moyennes 17 Mo, grandes 52 Mo), **43 s** avec 4 processus. *Écarté pour l'instant :* AVIF (encodage bien plus lent, gain modeste à ces tailles) ; on pourra l'ajouter comme format supplémentaire sans toucher au modèle.
- **Aucune métadonnée par construction** : les pixels sont recopiés dans une image neuve, et `save()` ne reçoit jamais `exif`, `xmp` ni `icc_profile` (Pillow ne les écrit dans un WebP que si on les lui passe). Vérifié par des tests (lecture Pillow, absence des blocs RIFF `EXIF`/`XMP `/`ICCP`, exiftool) et par exiftool sur tout le cache du Japon.
- **Conversion en sRGB** via LittleCMS quand l'original a un profil ICC (Display P3 des iPhone), puisque le profil n'est pas conservé.
- **CR2** : rendu à partir du JPEG pleine taille (5184×3456) qu'il embarque, que Pillow décode comme un TIFF. *Écarté :* rawpy/libraw (dépendance lourde, développement RAW inutile ici).
- **Orientation** : `ImageOps.exif_transpose` pour JPEG et CR2 ; pour un HEIC, libheif applique la rotation au décodage. Vérifié sur les 32 photos tournées du Japon (90°, 180°, miroir).
- **ThumbHash** pour le placeholder (~25 octets en base64), plutôt que BlurHash : il encode le ratio et rend mieux les dégradés. **Encodeur porté en Python dans `voyages/thumbhash.py`** (référence d'Evan Wallace, MIT), vérifié octet pour octet contre le paquet npm `thumbhash` qui le décodera côté front. *Écarté :* `thumbhash-python`, qui impose Pillow < 11.
- **Couleur dominante** : couleur la plus fréquente après réduction à 5 couleurs (median cut) d'une vignette de 64 px.
- **Modèle** : `largeur`, `hauteur`, `couleur`, `placeholder` et `rendus_etag` sur **Photo** (un par photo), et entité **Rendu** par taille (dimensions, octets, chemin). Écart avec le cadrage, qui mettait couleur et placeholder sur Rendu.
- **Relance** : une photo est retraitée si `rendus_etag ≠ etag`, si un de ses fichiers manque, ou avec `--force`. L'etag (haché) est dans le nom du fichier : l'URL change quand l'original change, ce qui permet un cache navigateur `immutable`. Les anciens fichiers sont supprimés après une régénération réussie ; une photo illisible est signalée, et retentée à la prochaine relance.
- **Parallélisme** : `ProcessPoolExecutor` (fork), un client WebDAV par processus. Les processus fils téléchargent en mémoire et écrivent les fichiers ; **seul le processus principal écrit en base**. *Écarté :* Celery (pas de besoin d'asynchrone tant que l'import est lancé à la main).
- **API minimale** `GET /api/voyages/<slug>/photos/`, en lecture seule, sans coordonnées GPS ni chemin Nextcloud. L'étape 4 la complètera.
- **Service des rendus** : en dev, Django (`static()` si DEBUG) et le proxy Vite `/media`. **Proposition pour la prod (étape 7, non implémentée)** : un conteneur `nginx:alpine` qui monte le volume `rendus` en lecture seule et sert `/media/` avec `Cache-Control: public, max-age=31536000, immutable` ; NPM route `/media/` vers lui et le reste vers le front et Django. Nginx plutôt que Caddy parce que NPM est déjà basé sur nginx : une seule syntaxe à connaître.
- **exiftool dans l'image backend**, pour le test et le contrôle manuel. À réévaluer pour l'image de prod (étape 7).
