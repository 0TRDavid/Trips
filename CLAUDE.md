Cadrage – Carnet de voyages photo (agent Claude)
18 nov. 2026 · @DD
Vision et objectifs
Un carnet de voyages privé et auto-hébergé, qui reconstruit chaque voyage à partir des métadonnées des photos, et où tu écris le récit jour par jour. Il est conçu pour durer : tes futurs enfants doivent pouvoir le parcourir, puis y consigner leurs propres voyages.
• Priorité n°1 : une expérience visuelle soignée, avec des animations sur chaque page.
• Objectif d'apprentissage : piloter un agent Claude Code de bout en bout, toi en superviseur.
• Ce que le projet ne fait pas : remplacer Nextcloud pour le stockage, ni Memories pour la galerie brute.
Périmètre
La v1 couvre le voyage au Japon de bout en bout, en accès privé via Tailscale. Le reste attend que la base tienne.
v1 — le Japon, privé
• Import d'un dossier de voyage depuis Nextcloud (WebDAV) : date, GPS, appareil
• Regroupement automatique des photos par jour, dans le fuseau horaire du voyage
• Récit par voyage et par jour, légende par photo, saisis dans l'admin Django
• Pages : accueil (les voyages), voyage (carte simple + timeline), jour (récit + photos), photo en plein écran
• Animations de transition sur chaque page
• Cache de versions web des photos, sans données GPS
v2 — pendant les prochains voyages
• Écriture depuis le téléphone, via une interface adaptée au mobile (hors admin)
• Import incrémental des nouvelles photos synchronisées par Nextcloud
• Carte personnalisée : style sur mesure, tracé du parcours animé
• Vidéos courtes
Plus tard
• Plusieurs auteurs (tes enfants, chacun avec ses voyages)
• Ouverture sur internet, en lecture seule
• Export pérenne (site statique ou PDF) pour l'archivage
Architecture technique
Nextcloud reste la source des photos : le site ne stocke que les récits, les métadonnées et des versions web légères.
Tu accèdes au site par Tailscale et NPM. Django lit les photos dans Nextcloud en lecture seule et n'en garde que des versions web sans GPS. Claude Code travaille dans la VM pendant que tu supervises en SSH.
Stack : React + TypeScript (Vite), Motion et GSAP côté front ; Django, DRF, PostgreSQL, Pillow et pillow-heif côté back ; le tout en Docker Compose.
Modèle de données
Quatre entités suffisent pour la v1. L'auteur est présent dès le départ pour accueillir d'autres auteurs plus tard sans migration lourde.
Entité
Champs clés
Remarques
Voyage
auteur, titre, slug, dates de début et de fin, fuseau horaire, photo de couverture, récit d'introduction
Le fuseau sert à regrouper les photos par jour local
Jour
voyage, date, titre, récit, lieu principal
Récit en Markdown : lisible et exportable dans 20 ans
Photo
jour, chemin Nextcloud, etag, date de prise (UTC), lat/lon, altitude, appareil, orientation, légende, ordre, favori, visible
L'etag évite de réimporter une photo déjà traitée
Rendu
photo, type (miniature, web), format, largeur, hauteur, couleur dominante, placeholder flou
Généré à l'import, sans GPS ; sert aussi aux animations de chargement
Les récits n'existent nulle part ailleurs : la base doit être sauvegardée dès la mise en service (voir la section Sauvegarde).
Animations et expérience visuelle
C'est ton critère n°1 : les animations sont une exigence dès la v1, avec leurs outils choisis dès le départ, pas une finition ajoutée à la fin.
Outils
• Motion (ex-Framer Motion) : transitions entre pages, et surtout la continuité d'un élément d'une page à l'autre (la vignette d'un voyage qui s'ouvre en plein écran).
• GSAP + ScrollTrigger : animations pilotées par le défilement, pour raconter une journée au fil du scroll.
• Lenis (optionnel) : défilement fluide, qui rend le scroll plus doux.
Idées par page
Page
Animation envisagée
Accueil
Les cartes des voyages s'ouvrent en plein écran au clic
Voyage
Le tracé du parcours se dessine au fil du défilement, les jours apparaissent un à un
Jour
Photos en parallaxe, texte révélé progressivement
Photo
Zoom continu depuis la vignette, navigation par glissement
Ce qui rend les animations fluides
• Couleur dominante et placeholder flou calculés à l'import : la page s'anime avant que l'image soit chargée.
• Images aux bonnes dimensions (AVIF ou WebP, plusieurs tailles), pour ne jamais charger un original de 5 Mo.
• Respect du réglage « réduire les animations » du système (prefers-reduced-motion).
Avec l'agent : une animation se juge à l'œil, pas en relisant du code. Rassemble 3 à 5 sites qui te plaisent (Awwwards est une bonne source), décris l'intention page par page, puis itère par petites boucles : l'agent livre, tu regardes, tu commentes.
Cartes (plus tard) : MapLibre GL avec un style sur mesure (éditable avec Maputnik) plutôt que les tuiles OpenStreetMap standard, plus un tracé animé. La source des tuiles reste à choisir.
Environnement de l'agent
L'agent travaille dans une VM dédiée qui lui sert de bac à sable : il y a des droits larges, mais il ne voit rien d'autre de ton réseau, et un snapshot Proxmox permet de revenir en arrière à chaque étape.
Élément
Choix
VM
Debian, 2 vCPU, 4 Go de RAM, 40 Go de disque (à ajuster selon les ressources libres du NUC)
Outils
Docker + Compose, Git, Node LTS, Python 3.12+, Claude Code
Connexion Claude
Ton abonnement via /login ; aucune variable ANTHROPIC_API_KEY sur la VM
Réseau
Règle OPNsense : internet (API Anthropic, npm, pip, GitHub) et Nextcloud uniquement ; ni Proxmox, ni OPNsense, ni Vaultwarden
Nextcloud
Utilisateur dédié, dossier Voyages partagé en lecture seule, mot de passe d'application propre à cet utilisateur
Secrets
Dans .env, exclu de Git ; aucun identifiant d'administration sur la VM
Ton accès
SSH via Tailscale ; VS Code Remote-SSH pour relire les diffs confortablement
Hébergement v1
Dev dans la VM de l'agent ; le site en service tourne sur ta machine Docker existante, publié via NPM
Permissions de Claude Code : commence en mode par défaut (il demande avant chaque commande) pour voir comment il travaille, puis autorise les modifications de fichiers sans confirmation. Le mode sans aucune confirmation n'est acceptable que parce que la VM est isolée et sauvegardée par snapshot.
Méthode de travail
Tu décides quoi faire et tu valides ; l'agent planifie, code et teste. Chaque étape suit la même boucle :
1.  Spec (toi) : 5 à 10 lignes, avec l'objectif et les critères qui diront que c'est fini.
2.  Plan (l'agent, en mode plan) : il propose une approche, tu la valides ou la corriges.
3.  Snapshot Proxmox, puis l'agent code sur une branche dédiée, avec des tests.
4.  Revue (toi) : tu lis le diff, tu testes dans le navigateur, tu commentes.
5.  Clôture : fusion dans main, puis l'agent met à jour CLAUDE.md et le journal des décisions.
Règles
• Une étape = une branche = un objectif vérifiable.
• Session neuve (/clear) entre deux étapes : le contexte utile vit dans CLAUDE.md, pas dans l'historique de la conversation.
• Si une étape part dans le mauvais sens, restaure le snapshot et reformule la spec plutôt que de rafistoler.
• Ce que tu corriges deux fois devient une règle dans CLAUDE.md.
Découpage en étapes
Huit étapes mènent à la v1, chacune avec un critère de fin que tu peux vérifier toi-même.
#
Étape
Terminée quand…
0
Environnement : VM, Claude Code, dépôt, CLAUDE.md
L'agent lance un projet vide avec docker compose up
1
Squelette : Django + DRF + PostgreSQL, React + TypeScript (Vite), compose de dev
Une page d'accueil s'affiche depuis ton PC via Tailscale
2
Import Nextcloud : commande import_voyage <dossier> (WebDAV, métadonnées, regroupement par jour), relançable sans doublons
Le Japon est importé et le nombre de photos correspond à Nextcloud
3
Rendus : miniatures et versions web sans GPS, couleur dominante, placeholder
Aucune image servie ne contient de coordonnées GPS
4
Admin et API : récits du voyage et des jours, légendes
Tu écris le récit d'une journée dans l'admin
5
Front fonctionnel : accueil, voyage (carte simple + timeline), jour, photo
Tu parcours tout le voyage sans bug, même sans animations
6
Passe animations, page par page
Chaque page est validée par toi, à l'œil
7
Mise en service sur la machine Docker : compose de prod, NPM, sauvegarde de la base, doc de redéploiement dans homelab-stack
Le site survit à un redémarrage et une sauvegarde restaurée fonctionne
La v2 (écriture sur mobile, import incrémental, carte personnalisée) démarre une fois l'étape 7 validée.
CLAUDE.md de départ
À placer à la racine du dépôt avant l'étape 0. L'agent le lit au début de chaque session et le complète au fil des étapes.
# Carnet de voyages

## Contexte
Site privé (accès Tailscale uniquement) qui retrace mes voyages à partir
des métadonnées des photos stockées dans Nextcloud, avec un récit écrit
jour par jour. Il doit durer des années et accueillir plus tard d'autres
auteurs (mes enfants). L'expérience visuelle et les animations sont la
priorité n°1.

## Rôles
- Toi (Claude) : tu conçois, tu codes, tu testes.
- Moi : je valide les plans, je relis les diffs, je teste dans le navigateur.
- Je ne code pas le front : explique tes choix React quand ils ne sont pas évidents.

## Stack
- Backend : Django + Django REST Framework, PostgreSQL
- Frontend : React + TypeScript (Vite), Motion, GSAP
- Photos : Nextcloud via WebDAV, lecture seule, originaux jamais copiés ; un dossier par voyage, un sous-dossier par photographe (`Japon 2025/Hugo/…`, `Japon 2025/David/…` → `Photo.photographe`), HEIC, JPEG et CR2 ; vidéos .mp4/.mov ; photos animées Samsung (HEIC + boîte `mpvd`)
- Déploiement : Docker Compose, derrière Nginx Proxy Manager

## Règles
- Une étape = une branche `etape-N-<nom>`. Jamais de commit direct sur `main`.
- Commence chaque étape en mode plan et attends ma validation avant de coder.
- Les images servies ne contiennent jamais de métadonnées GPS.
- Dates de prise de vue stockées en UTC, affichées dans le fuseau du voyage.
- Récits en Markdown.
- Secrets uniquement dans `.env`, jamais commité.
- Originaux Nextcloud lus en mémoire seulement, jamais écrits sur disque.
- Tests obligatoires pour l'import et l'extraction des métadonnées.
- N'accède à aucune machine du réseau en dehors de Nextcloud.
- Animations : respecte `prefers-reduced-motion`.
- Rendus : WebP générés par `voyages/rendus.py`, jamais d'EXIF/XMP/ICC passés à `save()` ; le cache est régénérable, seule la base est irremplaçable.
- Médias : la classe `Photo` porte un `type` (`photo`, `animee`, `video`) ; on ne la renomme pas. Vidéos lues par ffmpeg/ffprobe en flux sur WebDAV (`client.entree_video`), vidéo d'une photo animée par `memfd` (`video.entree_memoire`) : jamais de fichier temporaire. Rendus MP4 par `voyages/rendus_video.py` uniquement (`-map` explicites, `-map_metadata -1`, `-dn`, HDR converti en SDR) ; poster d'une vidéo = `produire_rendus()` sur une image extraite.
- Nouvelle analyse à l'import (ex. un nouveau format à détecter) : incrémenter `VERSION_ANALYSE` dans `importation.py` ; les photos concernées sont relues une fois.
- Après un changement de `vite.config.ts` : `docker compose restart frontend`.
- Après la création d'un nouveau module Python jamais importé (ex. `admin.py`) : `docker compose restart backend` (runserver ne le surveille pas encore).
- Markdown : un seul moteur, `voyages/markdown.py: rendre_markdown()` (API, aperçu admin, futur export). Le HTML écrit dans un récit n'est jamais interprété.
- API en lecture seule, sans N+1 : chaque endpoint a un nombre de requêtes fixe, vérifié par `NombreDeRequetesTests` (à mettre à jour si on ajoute une requête). Jamais de chemin Nextcloud, d'etag ni de coordonnées par photo dans l'API.
- Voyages, jours et photos naissent de l'import : l'admin ne les crée ni ne les supprime. Seule exception : l'écran « Compléter » crée le jour où l'on déplace un média ; il ne supprime jamais un jour vidé (déjà invisible sur le site).
- Date et position d'un média portent leur source (`source_date` : `exif`, `nom_fichier`, `manuel` ou vide = date du fichier, provisoire ; `source_position` : `exif`, `manuel` ou vide). Une valeur `manuel` n'est **jamais** écrasée par l'import. Écritures manuelles uniquement via `voyages/completion.py` (changement de jour + insertion chronologique + dates du voyage) ; noms WhatsApp analysés par `voyages/noms.py` (date proposée, `date_a_confirmer`, média masqué tant qu'elle n'est pas confirmée).
- Écriture dans Nextcloud **uniquement sous `NEXTCLOUD_DOSSIER_EXPORT`** (`Shared/Métadonnées`, garde-fou `ClientWebDAV.verifier_ecriture`, jamais un dossier de voyage). Les saisies manuelles y partent en sidecars XMP (`voyages/xmp.py`, `export_xmp.py`), lancés en arrière-plan après chaque action de l'écran Compléter ; les originaux ne sont jamais modifiés.
- Géocodage : Nominatim via `voyages/geocodage.py` uniquement (cache `LieuCherche`, 1 requête/s, pas d'autocomplétion, User-Agent sans donnée personnelle, contact facultatif `NOMINATIM_CONTACT`).
- Front : toute photo passe par `composants/Photo.tsx` (srcset, ratio réservé, couleur + ThumbHash) ; une photo animée par `PhotoAnimee.tsx`, une vidéo dans la visionneuse par `LecteurVideo.tsx`, qui posent leur `<video>` dans `Photo` (prop `children`). Photo animée jouée une seule fois à son apparition, puis image fixe ; lecture automatique seulement sans `prefers-reduced-motion` (`hooks/useMouvementReduit.ts`). URL construites par `lib/chemins.ts`. Éléments partagés entre pages marqués `data-transition-id` via `lib/transitions.ts`.
- Carte : MapLibre + OpenFreeMap, chargée en lazy ; ne pas retirer `setWorkerUrl` dans `CarteParcours.tsx`.
- Mouvement : durées, courbes et ressorts **uniquement** dans `frontend/src/lib/mouvement.ts` (jamais de valeur en dur dans un composant ; en CSS, `var(--duree-…)`). On n'anime que `transform` et `opacity`, **écrits tels quels** (`decaler()`, jamais `x`/`y`/`scale` de Motion, calculés sur le fil principal) pour que le navigateur les joue hors du fil principal ; une entrée finit par `transitionEnd: { transform: "none" }` (test Vitest) ; une sortie est plus courte que son entrée ; le sens vient de `lib/navigation.ts` (sémantique : le retour du navigateur rejoue l'inverse). Transitions de pages dans `Layout.tsx` (AnimatePresence, page sortante figée en `position: fixed`). Élément partagé = `useVolEntrant` + `lib/vol.ts` (clone FLIP avec contre-échelle, trajectoire précalculée jouée par `element.animate`, jamais `layoutId`). Paires partagées (`lib/transitions.ts`) : carte → en-tête du voyage, vignette de la timeline → couverture du jour, miniature → plein écran. Ce qui est lourd à monter pendant un vol (carte, galerie du jour) attend `useApresVol()`. Mouvement réduit : `useMouvementReduit()` / `mouvementReduit()`, tout devient un fondu.
- Couleurs : palette d'un voyage ou d'un jour calculée par le serveur (`voyages/palette.py`, OKLCH, contraste AA testé), appliquée par `usePalette()` (`layout/contexte.ts`) en variables CSS : `--accent` = texte accentué, `--accent-vif` = surfaces et filets (jamais de petit texte), `--sur-accent` = texte sur `--accent-vif`, `--papier`/`--papier-2` = fonds, `--degrade`, `--halo-1..3` = halos du fond (`FondPage`). Nouvelle couleur de texte = vérifier son contraste sur `--papier-2` et les halos (`TEXTES_NEUTRES` dans `palette.py`).

## Commandes
- `cp .env.example .env` : première fois seulement, puis changer les secrets
- `docker compose up -d --build` : lance l'environnement de dev (db, backend :8000, frontend :5173)
- `docker compose logs -f backend` (ou `frontend`) : suivre les logs
- `docker compose exec backend python manage.py test` : tests backend
- `docker compose exec frontend npm run build` : vérification TypeScript + build (puis `docker compose exec frontend rm -rf dist`, le dossier appartient à root)
- `docker compose exec frontend npm test` : tests Vitest du front (logique pure : srcset, dates, carte, glissement)
- `docker compose exec backend python manage.py createsuperuser` : compte admin (`/admin/`)
- `docker compose exec backend python manage.py import_voyage "<dossier>" --fuseau Asia/Tokyo [--horloge "Canon EOS 100D=UTC"] [--horloge "nom de fichier=Europe/Paris"] [--titre ...] [--ancien-dossier "<ancien chemin>"] [--limite N] [--dry-run]` : importe ou réimporte un dossier Nextcloud (chemin depuis la racine de l'utilisateur, ex. `/Shared/Japon 2025`). Relançable sans doublons ; `--fuseau` seulement au premier import ; le rapport final compare Nextcloud et la base.
  Une photo déplacée entre sous-dossiers (même etag + même nom) garde son identité. Dossier du voyage renommé dans Nextcloud : l'import refuse (photos déjà connues) et indique la commande avec `--ancien-dossier`. Faire d'abord un `--dry-run`.
  `--horloge "nom de fichier=…"` : une vidéo nommée `AA-MM-JJ HH-MM-SS…` est datée par son nom (exports de Hugo, dont la date interne est fausse). Japon : posé, Europe/Paris.
  Médias sans date (WhatsApp de Valérie) : importés masqués, à la date du fichier ; un jour qui n'a que des médias masqués n'apparaît pas sur le site.
  Génère ensuite les rendus web du voyage (sauf `--sans-rendus`) ; pour un gros encodage, préférer `--sans-rendus` puis `generer_rendus --processus 2` (mémoire de la VM).
- `docker compose exec backend python manage.py generer_rendus [--voyage <slug>] [--photos 1,2,3] [--force] [--processus N] [--dry-run]` : rendus WebP (400 / 1280 / 2560 px, sans métadonnées) et MP4 H.264 (petit côté 720 et 1080, jamais agrandi, 30 i/s max, sans son pour une photo animée) dans le volume `rendus` (`/cache/rendus/<photo_id>/<etag>-<taille>.webp|mp4`). Deux pistes indépendantes (`rendus_etag`, `videos_etag`) : ne régénère que ce dont l'etag a changé ou dont un fichier manque. Japon (660 médias) : premier passage ~25 min avec `--processus 2`, cache 2,4 Go (dont MP4 des photos animées 1,1 Go, des vidéos 0,76 Go).
- `docker compose exec backend python manage.py calculer_couleurs [--voyage <slug>] [--force]` : couleurs vives des médias (`Photo.couleurs`), lues dans les miniatures du cache (ni Nextcloud ni original). Fait automatiquement par `generer_rendus` pour les nouveaux médias ; à lancer pour l'existant.
- `docker compose exec backend sh -c 'exiftool -q -a -s -gps:all -userdata:all -keys:all /cache/rendus/*/*.webp /cache/rendus/*/*.mp4'` : contrôle qu'aucun rendu ne contient de GPS (ne doit rien afficher)
- API (lecture seule, `API_ACCES` dans `.env` : `prive-reseau` ou `connecte`) :
  - `GET /api/voyages/` : voyages, dates, `nb_jours`, `nb_photos`, couverture (choisie, sinon premier favori, sinon première photo), `palette` (aussi sur le détail d'un voyage, chaque jour résumé et le détail d'un jour : `accent`, `accent_texte`, `sur_accent`, `fond`, `fond_2`, `degrade`, `halos`)
  - `GET /api/voyages/<slug>/` : + récit d'intro (`recit_intro` et `recit_intro_html`), jours résumés, `trace` GPS allégé `[{lat, lon, jour}]`
  - `GET /api/voyages/<slug>/jours/<AAAA-MM-JJ>/` : récit (Markdown + HTML), médias visibles dans l'ordre (`prise_le` avec le décalage du voyage ; `type`, `duree`, `videos` {"720", "1080"} ; `rendus` = image ou poster), `precedent` / `suivant`
  - `GET /api/voyages/<slug>/photos/` : toutes les photos visibles du voyage
- Admin `/admin/` : Voyage (couverture en grille, jours restant à écrire), Jour (éditeur Markdown EasyMDE avec aperçu serveur, photos réordonnables par glisser-déposer sur la bande grise), Média (filtre par type et par source, lecteur vidéo dans la fiche) ; action « Régénérer les rendus » (lancée en arrière-plan, suivi dans `docker compose logs -f backend`).
- Admin `/admin/voyages/photo/completer/` (bouton « Compléter dates et positions » de la liste des médias) : médias sans date fiable ou sans position ; clic sur la carte MapLibre (copiée dans `voyages/static/voyages/maplibre/`), recherche de lieu, « placer entre » deux médias du jour, « reprendre » position/heure d'une voisine, heure saisie, confirmer la date proposée ; par média ou par lot. Endpoints JSON réservés à l'équipe dans `voyages/admin_completion.py` (hors API publique).
- `docker compose exec backend python manage.py exporter_xmp [--voyage <slug>] [--photos 1,2,3] [--dry-run]` : sidecars XMP (`<nom.ext>.xmp`, date et/ou position saisies à la main, avec leur source `carnet:`) dans `Shared/Métadonnées/<voyage>/xmp/<sous-dossier>/`. Ne réécrit que ce qui a changé (`Photo.xmp_empreinte`), relance = rattrapage des échecs (suivi de l'envoi automatique : `docker compose logs -f backend`).
- Ajout d'une dépendance front : `docker compose exec frontend npm install <paquet>` puis `docker compose up -d --build frontend`
- URL de dev : http://192.168.30.252:5173 (le proxy Vite relaie `/api` vers le backend)
- Routes du front : `/`, `/voyages/<slug>`, `/voyages/<slug>/jours/<date>`, `/voyages/<slug>/jours/<date>/photos/<id>` (visionneuse = route enfant du jour), 404 sinon
- `/labo` (dev uniquement, absent du build) : rejoue chaque transition dans deux iframes du vrai site (téléphone 390 × 844, ordinateur), ralenti, mouvement réduit simulé. Réglages en `localStorage` (`carnet-labo`). Pour comparer de futures variantes, les y remettre temporairement ; une fois validée, la variante devient la valeur des tokens et les autres sont retirées.

## Décisions
Consigne chaque décision structurante dans `docs/decisions.md`
(date, choix, raison, alternatives écartées).
Checklist de préparation
À faire avant de lancer l'agent sur l'étape 1.
[x] Créer la VM Debian sur Proxmox et prendre un premier snapshot
[x] Installer Docker, Git, Node LTS, Python et Claude Code
[x] Vérifier l'absence de ANTHROPIC_API_KEY, puis claude et /login avec l'abonnement
[x] Ajouter les règles OPNsense : internet et Nextcloud uniquement
[x] Créer l'utilisateur Nextcloud dédié, lui partager le dossier Voyages en lecture seule, générer son mot de passe d'application
[x] Créer le dépôt GitHub privé, donner à la VM une clé de déploiement limitée à ce seul dépôt, et y placer CLAUDE.md
[ ] Rassembler 3 à 5 sites de référence pour les animations
[ ] Rédiger la spec de l'étape 1
Sauvegarde
Les récits sont la seule donnée irremplaçable du site : le cache se régénère et les photos vivent dans Nextcloud. Nextcloud tourne sur le même NUC, donc une copie là-bas ne protège pas d'une panne : il faut aussi une copie hors du NUC.
Couche
Contenu
Fréquence
Destination
Dump de la base
pg_dump compressé
Chaque nuit ; 7 quotidiens et 4 hebdomadaires conservés
Machine Docker
Copie hors NUC
Les dumps, chiffrés avec restic
Chaque nuit, après le dump
Stockage objet (Backblaze B2 ou équivalent, coût négligeable pour quelques Mo) ou ton PC fixe
Export lisible
Récits en Markdown (un fichier par jour) + métadonnées en JSON
Chaque semaine
Dossier Nextcloud dédié, distinct de Voyages, en écriture pour l'utilisateur du site
• L'export Markdown est celui qui comptera dans 20 ans : lisible sans le site, même quand Django et React auront disparu.
• L'étape 7 inclut un test de restauration : un dump restauré sur une base vide, et un récit retrouvé.
• Hors périmètre, mais à vérifier : tes photos originales n'existent que dans Nextcloud, sur ce même NUC. Assure-toi qu'elles ont aussi une copie ailleurs.
Décisions et questions ouvertes
Sujet
Décision
Photos
Un dossier Nextcloud par voyage ; surtout du HEIC, parfois du JPEG : l'import gère les deux (pillow-heif)
Fuseau horaire
Téléphone réglé automatiquement à l'heure locale : les heures des photos sont déjà cohérentes, aucune correction à prévoir
Dépôt
GitHub privé
Hébergement
La VM sert au dev de l'agent ; le site en service tourne sur la machine Docker
Sauvegarde
Proposition dans la section Sauvegarde, à valider
• Cartes : rassembler quelques exemples de rendus qui te plaisent.
• Sauvegarde : choisir la cible hors du NUC (stockage objet ou PC fixe).
