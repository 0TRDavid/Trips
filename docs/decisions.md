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

## 2026-11-19 — Étape 4 (admin et API)

- **Markdown rendu côté serveur**, en HTML nettoyé : `markdown-it-py` (CommonMark, HTML brut désactivé) puis `nh3` (liste blanche : titres h2–h4, paragraphes, emphase, listes, citations, liens http/https/mailto en `rel="noopener noreferrer"`, code). Un seul moteur (`voyages/markdown.py`) pour l'API, l'aperçu de l'admin et le futur export. L'API renvoie la source **et** le HTML. *Écartés :* `react-markdown` côté front (un deuxième moteur, qui pourrait diverger de l'aperçu), `bleach` (déprécié), `python-markdown` (moins fidèle à CommonMark). Les images Markdown (`![]()`) sont volontairement retirées : les photos d'un récit viennent de la galerie.
- **Protection de l'API par un seul réglage**, `API_ACCES`, dans `voyages/permissions.py` :
  - Toutes les vues sont en lecture seule (GET), quel que soit le mode.
  - `prive-reseau` (v1) : ouvert, c'est Tailscale qui protège.
  - `connecte` : session Django exigée. Le front est sur la même origine, le cookie suffit, sans JWT ni CORS.
  - Authentification : session uniquement (Basic retiré).
  - **Le jour de l'ouverture sur internet (non implémenté)** : mode `public` (AllowAny, champ `Voyage.publie` qui filtre les voyages, `AnonRateThrottle`), `/admin/` joignable seulement via Tailscale (règle NPM), et `/media/` protégé en mode `connecte` par un `auth_request` nginx vers Django.
- **Pas de N+1** : comptes et photo représentative calculés en sous-requêtes SQL (`Subquery` + `Coalesce`, qui évitent la multiplication de lignes de plusieurs `Count()` sur des jointures), puis photos et rendus chargés en une fois. Requêtes par endpoint : liste 3, voyage 5, jour 6. Elles restent identiques quand on double le volume (test).
- **Photo représentative** (couverture de repli, vignette d'un jour, voisins) : premier favori visible, sinon première photo visible dans l'ordre. Une couverture choisie dans l'admin l'emporte toujours.
- **`prise_le` avec le décalage du voyage** dans la page d'un jour (`2025-06-02T10:00:00+09:00`). C'est le même instant que l'UTC stocké, mais le front l'affiche sans bibliothèque de fuseaux.
- **Tracé GPS** : photos visibles géolocalisées, triées par date, simplifiées par **Ramer-Douglas-Peucker jour par jour** (tolérance 30 m, projection locale en mètres), coordonnées arrondies à 5 décimales. Simplifier par jour garde exactes les frontières entre jours pour l'animation au défilement. Japon : 32 positions → 25 points. Le tracé inclut les étapes de départ (Lyon, Amsterdam) : masquer une photo la retire aussi du tracé. Pas de dépendance (une trentaine de lignes).
- **Ordre des photos** : django-admin-sortable2 (glisser-déposer sur la bande grise au-dessus de chaque photo, flèches ▲▼ pour envoyer en tête ou en fin). L'inline déclare son propre `ordering = ["ordre", "prise_le"]`, le `Meta.ordering` du modèle ne change pas. Une migration numérote `ordre` (1…n par jour, selon `prise_le`) : l'ordre affiché ne change pas. L'import range une nouvelle photo, ou une photo qui change de jour, à la fin du jour, sans toucher aux autres. *Écarté :* écrire du JS de glisser-déposer à la main.
- **Éditeur Markdown : EasyMDE 2.21.0 copié dans `voyages/static/`** (MIT, pas de CDN). L'aperçu (onglet ou côte à côte) est demandé au serveur (`POST /admin/voyages/voyage/apercu-markdown/`, réservé à l'équipe, CSRF), il est donc identique au site. Les boutons sont en texte (pas de Font Awesome). Mode de saisie `textarea` de CodeMirror : le mode `contenteditable`, qui aurait permis le correcteur orthographique du navigateur, perdait les caractères accentués à la frappe en test. Fins de ligne normalisées en `\n` à l'enregistrement. *Écartés :* django-markdownx (aperçu moins pratique), Toast UI Editor (bien plus lourd).
- **Couverture** : boutons radio en grille de miniatures, limités aux photos du voyage, avec « Automatique » (repli décrit plus haut). On n'utilise pas l'enveloppe « ajouter / modifier » de l'admin pour ce champ.
- **Admin sans création ni suppression** de voyages et de jours (ils naissent de l'import, et leurs récits n'existent nulle part ailleurs), ni de photos (une photo disparue est signalée par l'import). La suppression reste possible en shell si un jour c'est voulu.
- **Action « Régénérer les rendus »** (voyages, jours, photos) : lance `generer_rendus --force --photos <ids>` dans un **processus détaché** (`subprocess.Popen`, `start_new_session`), dont la sortie va dans les logs du backend. Un voyage entier (~45 s) dépasse le délai d'une requête HTTP, et forker un pool de processus depuis le serveur web est risqué. *Écarté :* Celery (pas de besoin d'asynchrone au-delà de cette action). Limite connue : pas de retour dans l'admin quand c'est fini, il faut regarder les logs.
- **Libellés français** sur tous les modèles et champs (`verbose_name`, migration sans effet sur les données). Admin titré « Carnet de voyages », app « Carnet ».

## 2026-11-20 — Étape 5 (front fonctionnel)

- **React Router 8 en mode « data router »** (`createBrowserRouter`), routes imbriquées sous un `Layout` commun jamais démonté. La visionneuse est une **route enfant** de la page jour (`…/jours/<date>/photos/<id>`) : la page jour reste montée dessous (défilement conservé, rien à recharger) et un lien direct vers une photo affiche aussi le jour derrière. *Écarté :* le motif « background location » (modale sur une route sœur), plus compliqué pour le même résultat ici.
- **Historique de la visionneuse** : ouvrir une photo ajoute une entrée ; ← / → / glissement la **remplacent** (sinon 30 photos vues = 30 « retour » pour sortir) ; Échap / ✕ font `history.back()` si on vient de la galerie, sinon (lien direct) remplacent l'URL par celle du jour. À la fermeture, la miniature de la dernière photo vue est ramenée à l'écran.
- **Sélection d'un jour sur la carte hors de l'URL** : état d'écran éphémère ; le retour arrière ramène à la page précédente, pas au zoom d'avant.
- **TanStack Query 5** pour le cache (5 min, pas de rechargement au focus, pas de nouvel essai sur une 404). Les jours voisins sont préchargés, et un jour l'est au survol de son lien : passer d'un jour à l'autre est instantané. La visionneuse lit les photos dans le cache de la page jour, sans requête.
- **Carte : MapLibre GL 6 + tuiles vectorielles OpenFreeMap** (style `positron`), gratuites, sans clé ni compte. Le vectoriel permettra un style maison (Maputnik) sur les mêmes tuiles à la v2. *Écartés :* tuiles raster OSM (politique d'usage, pas de style), MapTiler/Stadia (clé), PMTiles auto-hébergé (piste pour plus tard). Le navigateur appelle `tiles.openfreemap.org` directement : aucune règle réseau à changer sur la VM.
  - Le worker de MapLibre est passé explicitement (`setWorkerUrl` + import `?url`) : sinon il est cherché à côté du fichier regroupé par Vite et ne se charge pas.
  - La carte est **chargée à la demande** (`React.lazy`) : ~290 Ko gzip qui ne pèsent ni sur l'accueil ni sur les jours (bundle principal ~118 Ko gzip).
  - « Zoomer sur les photos d'un jour » = cadrer les points du tracé de ce jour (l'API ne donne pas de coordonnées par photo) ; un seul point → zoom fixe ; aucun point → la carte ne bouge pas, mention « sans position ».
  - Téléphone : carte collante en haut, gestes coopératifs (un doigt fait défiler la page, deux doigts bougent la carte).
- **Composant photo unique** (`composants/Photo.tsx`) : boîte au ratio exact (`aspect-ratio`), fond = couleur dominante puis ThumbHash décodé (`thumbhash`, la lib de référence de l'encodeur Python), `srcset` des trois rendus avec `sizes`, image affichée une fois chargée. Trois modes : naturel, couvrir, contenir (requêtes de conteneur `cqw/cqh` pour que la boîte colle à la photo dans la visionneuse). CLS mesuré à 0 sur toutes les pages.
- **Galerie en rangées justifiées en CSS pur** (`flex-grow` ∝ ratio, multiplié par 100 car une rangée dont la somme des `flex-grow` est < 1 ne se remplit pas). *Écarté :* calcul JS des rangées (mesure de largeur, risque de saut au premier rendu).
- **Glissement maison** (Pointer Events, ~50 lignes, ignore souris et pincement) plutôt que Motion, installé mais réservé à l'étape 6.
- **Préparation de l'étape 6** : `Layout` récupère la page via `useOutlet()` avec une clé par page (`clePage`, qui ignore la visionneuse) : il suffira d'y ajouter `AnimatePresence`. Attribut `data-transition-id` identique au départ et à l'arrivée (`voyage-<slug>` carte → en-tête, `photo-<id>` miniature → plein écran), via `lib/transitions.ts`.
- **CSS Modules** (natif Vite) et variables dans `styles/tokens.css` (palette et typo provisoires : Fraunces + Inter, auto-hébergées via Fontsource, aucune requête vers Google). `scrollbar-gutter: stable` : la page ne se décale pas quand la visionneuse bloque le défilement.
- **Tests** : Vitest pour la logique pure (srcset, dates, cadrage de carte, décision de glissement). Vérification visuelle et parcours (clavier, retour navigateur, lien direct, glissement, 10 jours) par un script Playwright hors dépôt ; le Chrome attendu par le plugin Playwright n'est pas installé sur la VM, le Chromium de Playwright suffit.
