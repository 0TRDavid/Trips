"""Rendus web d'une vidéo : MP4 H.264 en 720p et 1080p, sans aucune métadonnée.

Comme `rendus.py`, ce module ne touche pas à la base : il reçoit une entrée
ffmpeg (flux WebDAV ou mémoire, voir `video.py`) et écrit dans le cache.

Ce qui garantit l'absence de métadonnées (GPS, date, appareil) :
- seules la première piste vidéo et, pour une vidéo, la première piste son
  sont gardées (`-map`) : les pistes de données (métadonnées Apple, qui
  portent le GPS), les sous-titres et les chapitres sont écartés ;
- `-map_metadata -1` vide les balises du conteneur et des pistes ;
- la rotation est appliquée aux pixels (autorotate) : aucune matrice
  d'affichage n'est recopiée.

Un seul décodage par source : le filtre `split` alimente les deux tailles,
encodées dans la même commande (le décodage HEVC et la conversion HDR sont
les étapes les plus coûteuses).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .rendus import FichierRendu, ResultatRendu, produire_rendus
from .video import Entree, InfosVideo, executer, infos_video, sonder

# Petit côté de chaque rendu, en pixels. On n'agrandit jamais : une source plus
# petite garde sa taille (une seule taille si elle ne dépasse pas 720).
TAILLES_VIDEO = {"video_720": 720, "video_1080": 1080}
# Cadence maximale : le 60 i/s des Samsung doublerait la taille pour un gain
# minime ici. Monter à 60 si le rendu paraît saccadé.
IPS_MAX = 30
CRF = 23
PRESET = "veryfast"
DEBIT_SON = "128k"
DELAI_ENCODAGE = 3 * 3600  # secondes, pour la plus longue vidéo
DELAI_IMAGE = 300

# HDR10 / HLG → SDR BT.709 (sinon l'image sort grise et délavée). Les
# métadonnées HDR (luminance d'étalonnage, niveau de lumière) sont retirées :
# recopiées dans un rendu SDR, elles le décriraient faussement.
CONVERSION_HDR = (
    "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,"
    "sidedata=mode=delete:type=MASTERING_DISPLAY_METADATA,"
    "sidedata=mode=delete:type=CONTENT_LIGHT_LEVEL"
)


@dataclass
class ResultatVideo:
    infos: InfosVideo
    fichiers: list[FichierRendu] = field(default_factory=list)


def _pair(valeur: float) -> int:
    """H.264 en 4:2:0 exige des dimensions paires."""
    return max(2, int(round(valeur / 2)) * 2)


def plan_tailles(largeur: int, hauteur: int) -> list[tuple[str, int, int]]:
    """[(taille, largeur, hauteur)] des rendus d'une vidéo affichée en largeur×hauteur.

    >>> plan_tailles(1080, 1920)   # Samsung vertical
    [('video_720', 720, 1280), ('video_1080', 1080, 1920)]
    >>> plan_tailles(984, 1312)    # photo animée : 1080 serait un agrandissement
    [('video_720', 720, 960), ('video_1080', 984, 1312)]
    >>> plan_tailles(480, 848)     # WhatsApp : une seule taille, native
    [('video_720', 480, 848)]
    """
    petit = min(largeur, hauteur)
    plan = []
    for taille, cible in sorted(TAILLES_VIDEO.items(), key=lambda t: t[1]):
        facteur = min(1.0, cible / petit)
        plan.append((taille, _pair(largeur * facteur), _pair(hauteur * facteur)))
        if facteur == 1.0:
            break  # la source est atteinte : les tailles suivantes seraient identiques
    return plan


def _filtre_commun(infos: InfosVideo) -> str:
    etapes = []
    if infos.hdr:
        etapes.append(CONVERSION_HDR)
    if infos.ips and infos.ips > IPS_MAX + 0.5:
        etapes.append(f"fps={IPS_MAX}")
    etapes.append("format=yuv420p")
    return ",".join(etapes)


def produire_videos(entree: Entree, racine: Path, prefixe: str, *, son: bool, infos: InfosVideo | None = None) -> ResultatVideo:
    """Écrit `<racine>/<prefixe>-video_720.mp4` (et 1080) et renvoie leurs infos."""
    infos = infos or infos_video(sonder(entree))
    plan = plan_tailles(infos.largeur, infos.hauteur)
    (racine / prefixe).parent.mkdir(parents=True, exist_ok=True)

    etiquettes = [f"v{i}" for i in range(len(plan))]
    graphe = f"[0:v:0]{_filtre_commun(infos)},split={len(plan)}" + "".join(f"[s{i}]" for i in range(len(plan)))
    for i, (_, largeur, hauteur) in enumerate(plan):
        graphe += f";[s{i}]scale={largeur}:{hauteur}:flags=lanczos,setsar=1[{etiquettes[i]}]"

    commande = ["ffmpeg", "-v", "error", "-nostdin", "-y", *entree.args, "-filter_complex", graphe]
    sorties = []
    for (taille, largeur, hauteur), etiquette in zip(plan, etiquettes):
        relatif = f"{prefixe}-{taille}.mp4"
        temporaire = racine / f"{relatif}.tmp"
        commande += ["-map", f"[{etiquette}]"]
        if son and infos.a_son:
            commande += ["-map", "0:a:0", "-c:a", "aac", "-b:a", DEBIT_SON, "-ac", "2"]
        commande += [
            "-c:v", "libx264", "-preset", PRESET, "-crf", str(CRF), "-profile:v", "high",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-map_metadata", "-1", "-map_chapters", "-1", "-sn", "-dn",
            "-movflags", "+faststart", "-f", "mp4", str(temporaire),
        ]
        sorties.append((taille, relatif, temporaire, largeur, hauteur))

    try:
        executer(commande, entree, DELAI_ENCODAGE)
        resultat = ResultatVideo(infos=infos)
        for taille, relatif, temporaire, largeur, hauteur in sorties:
            # Écriture atomique : un rendu à moitié écrit n'est jamais visible.
            os.replace(temporaire, racine / relatif)
            octets = (racine / relatif).stat().st_size
            resultat.fichiers.append(FichierRendu(taille, relatif, largeur, hauteur, octets))
        return resultat
    finally:
        for *_, temporaire, _, _ in sorties:
            temporaire.unlink(missing_ok=True)


def image_apercu(entree: Entree, infos: InfosVideo) -> bytes:
    """Image d'aperçu (poster) en PNG, prise à min(1 s, durée / 2), rotation et HDR traités."""
    instant = min(1.0, (infos.duree or 0) / 2)
    filtre = ",".join(filter(None, [CONVERSION_HDR if infos.hdr else "", "format=rgb24"]))
    commande = [
        "ffmpeg", "-v", "error", "-nostdin", "-ss", f"{instant:.2f}", *entree.args,
        "-map", "0:v:0", "-frames:v", "1", "-vf", filtre, "-f", "image2pipe", "-c:v", "png", "-",
    ]
    png = executer(commande, entree, DELAI_IMAGE)
    if not png:
        raise ValueError("aucune image extraite de la vidéo")
    return png


def produire_apercu(entree: Entree, racine: Path, prefixe: str, infos: InfosVideo) -> ResultatRendu:
    """Poster d'une vidéo : WebP en trois tailles, couleur et ThumbHash, par la
    chaîne des photos (`rendus.produire_rendus`). Le PNG reste en mémoire."""
    return produire_rendus(image_apercu(entree, infos), racine, prefixe)
