"""core/sprite_engine.py – Moteur de sprites compatible Shimeji-ee"""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QPixmap, QTransform
from PyQt6.QtCore import Qt


@dataclass
class Pose:
    pixmap: QPixmap
    anchor_x: int
    anchor_y: int
    velocity_x: float
    velocity_y: float
    duration: int


@dataclass
class ActionDef:
    name:           str
    action_type:    str
    border_type:    str
    poses:          list = field(default_factory=list)
    loop:           bool  = True
    condition:      str   = ""
    gravity:        float = 3.5
    resistance_x:   float = 0.05
    resistance_y:   float = 0.1
    velocity_param: float = 35.0   # VelocityParam pour Jump actions
    ie_offset_x:    int   = 0      # WalkWithIE : offset X fenêtre / anchor
    ie_offset_y:    int   = -36    # WalkWithIE : offset Y fenêtre / anchor
    throw_initial_vx: float = 45.0 # ThrowIE : vitesse initiale horizontale
    throw_gravity:    float = 0.1  # ThrowIE : gravité de la fenêtre en vol


class SpriteEngine:
    """
    Charge et gère les sprites d'un personnage Shimeji-ee.

    Structures supportées :
        <character_path>/img/*.png  +  <character_path>/conf/actions.xml
        <character_path>/*.png      +  <character_path>/conf/actions.xml
        <character_path>/img/*.png  (sans XML → fallback)
    """

    def __init__(self, character_path: str, scale: float = 1.0):
        self.path = Path(character_path)
        self.scale = scale
        self.actions: dict[str, ActionDef] = {}
        self._pixmap_cache: dict[str, QPixmap] = {}

        # Dossiers de recherche des images (par ordre de priorité)
        self._img_dirs: list[Path] = self._resolve_img_dirs()
        print(f"[SpriteEngine] Dossiers images : {[str(d) for d in self._img_dirs]}")

        self._load_actions()

    # ------------------------------------------------------------------
    # Résolution des chemins
    # ------------------------------------------------------------------

    def _resolve_img_dirs(self) -> list[Path]:
        """Retourne tous les dossiers où chercher les PNG."""
        candidates = [
            self.path / "img",
            self.path,
            self.path.parent / "img",
            self.path.parent,
        ]
        return [p for p in candidates if p.exists() and p.is_dir()]

    def _find_image(self, name: str) -> Optional[Path]:
        """
        Cherche un fichier image dans tous les dossiers connus.
        Gère tous les formats courants dans les packs Shimeji :
          - "shime1.png"
          - "shime1"
          - "/img/shime1.png"
          - "./img/shime1.png"
          - "img/shime1.png"
          - "shime1" (sans extension, .png ajouté automatiquement)
        """
        # Extraire juste le nom de fichier (strip des chemins relatifs/absolus)
        basename = Path(name.replace("\\", "/")).name  # ex: "shime1.png"

        # Variantes à essayer
        variants: list[str] = []
        for n in [name, basename]:
            variants.append(n)
            if not n.lower().endswith(".png"):
                variants.append(n + ".png")
            # Certains packs utilisent .PNG majuscule
            if not n.lower().endswith(".png"):
                variants.append(n + ".PNG")

        # Dé-dupliquer en gardant l'ordre
        seen: set[str] = set()
        names_to_try: list[str] = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                names_to_try.append(v)

        for img_dir in self._img_dirs:
            for n in names_to_try:
                p = img_dir / n
                if p.exists():
                    return p

        # Recherche récursive (sous-dossiers) en dernier recours
        for img_dir in self._img_dirs:
            for n in names_to_try:
                found = list(img_dir.rglob(n))
                if found:
                    return found[0]

        return None

    # ------------------------------------------------------------------
    # Chargement des pixmaps
    # ------------------------------------------------------------------

    def _load_pixmap(self, name: str, flip: bool = False) -> Optional[QPixmap]:
        cache_key = f"{name}:{'flip' if flip else 'normal'}"
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        img_path = self._find_image(name)
        if img_path is None:
            # Dernier recours : cherche dans le dossier courant
            for ext in ["", ".png", ".PNG"]:
                p = Path(name + ext)
                if p.exists():
                    img_path = p
                    break

        if img_path is None:
            return None

        pm = QPixmap(str(img_path))
        if pm.isNull():
            return None

        if self.scale != 1.0:
            pm = pm.scaled(
                int(pm.width() * self.scale),
                int(pm.height() * self.scale),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        if flip:
            pm = pm.transformed(QTransform().scale(-1, 1))

        self._pixmap_cache[cache_key] = pm
        return pm

    # ------------------------------------------------------------------
    # Chargement XML
    # ------------------------------------------------------------------

    def _find_actions_xml(self) -> Optional[Path]:
        candidates = [
            self.path / "conf" / "actions.xml",
            self.path / "actions.xml",
            self.path.parent / "conf" / "actions.xml",
            self.path.parent / "actions.xml",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    @staticmethod
    def _get_attr(elem: ET.Element, *names: str, default: str = "") -> str:
        """
        Lit un attribut XML insensible à la casse.
        Shimeji original utilise des majuscules (Name, Image, ImageAnchor…)
        mais certains packs utilisent des minuscules.
        """
        for name in names:
            v = elem.get(name)
            if v is not None:
                return v
            # Essai insensible à la casse
            for k, val in elem.attrib.items():
                if k.lower() == name.lower():
                    return val
        return default

    @staticmethod
    def _strip_leading_slash(path: str) -> str:
        """Retire le slash initial des chemins Shimeji ('/idle1.png' → 'idle1.png')."""
        return path.lstrip("/\\")

    def _find_action_elements(self, root: ET.Element) -> list[ET.Element]:
        """
        Cherche les éléments <Action> quel que soit l'emboîtement.
        Supporte :
          <ActionList><Action>          (format simple)
          <Mascot><ActionList><Action>  (format Shimeji-ee standard)
          et les namespaces XML ({http://...}Action)
        """
        actions = []

        # Recherche récursive — ignore les namespaces
        def find_recursive(elem: ET.Element) -> None:
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "Action":
                actions.append(elem)
            for child in elem:
                find_recursive(child)

        find_recursive(root)
        return actions

    def _load_actions(self) -> None:
        xml_path = self._find_actions_xml()
        if xml_path is None:
            print("[SpriteEngine] Aucun actions.xml trouvé → fallback automatique")
            self._create_fallback_action()
            return

        print(f"[SpriteEngine] Chargement XML : {xml_path}")
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError as e:
            print(f"[SpriteEngine] Erreur XML : {e} → fallback")
            self._create_fallback_action()
            return

        root = tree.getroot()
        action_elems = self._find_action_elements(root)
        print(f"[SpriteEngine] {len(action_elems)} éléments Action trouvés dans le XML")

        for elem in action_elems:
            name        = self._get_attr(elem, "Name", "name", default="")
            action_type = self._get_attr(elem, "Type", "type", default="Stay")
            # Paramètres physiques (Falling action)
            try:
                gravity_str = self._get_attr(elem, "Gravity", "gravity", default="3.5")
                _m = re.search(r'[-\d.]+', gravity_str)
                gravity_val = float(_m.group()) if _m else 3.5
            except Exception:
                gravity_val = 3.5
            resistance_x = float(self._get_attr(elem, "RegistanceX","registanceX",default="0.05"))
            resistance_y = float(self._get_attr(elem, "RegistanceY","registanceY",default="0.1"))
            border_type = self._get_attr(elem, "BorderType", "borderType", default="Floor")
            loop_str    = self._get_attr(elem, "Loop", "loop", default="true")
            loop        = loop_str.lower() not in ("false", "0")
            # VelocityParam pour Jump actions
            try:
                velocity_param = float(self._get_attr(elem, "VelocityParam", "velocityParam", default="35.0"))
            except Exception:
                velocity_param = 35.0
            # WalkWithIE : IeOffsetX/Y
            try:
                ie_offset_x = int(self._get_attr(elem, "IeOffsetX", "ieOffsetX", default="0"))
                ie_offset_y = int(self._get_attr(elem, "IeOffsetY", "ieOffsetY", default="-36"))
            except Exception:
                ie_offset_x, ie_offset_y = 0, -36
            # ThrowIE : InitialVX + Gravity
            try:
                throw_initial_vx = float(self._get_attr(elem, "InitialVX", "initialVX", default="45.0"))
                throw_gravity    = float(self._get_attr(elem, "Gravity",   "gravity",   default="0.1"))
            except Exception:
                throw_initial_vx, throw_gravity = 45.0, 0.1

            if not name:
                continue

            # Pour Embedded: charger quand même les frames d'animation
            # (Shimeji utilise Java pour le mouvement mais les sprites sont dans le XML)
            # On ignore Embedded seulement si c'est Type="Embedded" sans animation définie ici
            # Note: le filtrage se fera après si poses=[]

            poses: list[Pose] = []

            # Cherche toutes les <Animation> (Pinched en a plusieurs conditionnelles)
            anim_list = []
            for child in elem:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "Animation":
                    anim_list.append(child)

            # Fallback : <Pose> directs sous <Action> sans wrapper <Animation>
            # (ex: Skadi Busy, certains packs custom)
            if not anim_list:
                direct_poses: list[ET.Element] = []
                for child in elem:
                    ctag = child.tag.split("}")[- 1] if "}" in child.tag else child.tag
                    if ctag == "Pose":
                        direct_poses.append(child)
                if direct_poses:
                    # On en fait un faux <Animation> virtuel pour le traitement unifié
                    anim_list = [direct_poses]  # type: ignore[assignment]

            if anim_list:
                # Pour Pinched : créer une action par Animation conditionnelle
                if name == 'Pinched' and len(anim_list) >= 2:
                    _pinch_names = ['pinch_l3','pinch_l2','pinch_l1','pinch_default',
                                    'pinch_r1','pinch_r2','pinch_r3']
                    for _pi, _panim in enumerate(anim_list):
                        if _pi >= len(_pinch_names):
                            break
                        _pposes = []
                        for _pe in _panim:
                            _ptag = _pe.tag.split('}')[-1] if '}' in _pe.tag else _pe.tag
                            if _ptag != 'Pose':
                                continue
                            _pimg = self._strip_leading_slash(
                                self._get_attr(_pe,'Image','image',default=''))
                            if _pimg:
                                _pm = self._load_pixmap(_pimg)
                                if _pm:
                                    _raw = self._get_attr(_pe,'ImageAnchor','imageAnchor','64,128').split(',')
                                    try:
                                        _ax = int(float(_raw[0]) * self.scale)
                                        _ay = int(float(_raw[1]) * self.scale)
                                    except Exception:
                                        _ax, _ay = 64, 128
                                    _pposes.append(Pose(_pm, _ax, _ay, 0.0, 0.0, 8))
                        if _pposes:
                            self.actions[_pinch_names[_pi]] = ActionDef(
                                name=_pinch_names[_pi], action_type='Stay',
                                border_type='Floor', poses=_pposes, loop=True)
                # Prendre le premier par défaut pour l'action principale
                anim = anim_list[0]
                for pose_elem in anim:
                    tag = pose_elem.tag.split("}")[-1] if "}" in pose_elem.tag else pose_elem.tag
                    if tag != "Pose":
                        continue

                    img_name = self._strip_leading_slash(
                        self._get_attr(pose_elem, "Image", "image", default="")
                    )

                    raw_anchor = self._get_attr(pose_elem, "ImageAnchor", "imageAnchor", default="0,0").split(",")
                    raw_vel    = self._get_attr(pose_elem, "Velocity",    "velocity",    default="0,0").split(",")
                    duration   = int(self._get_attr(pose_elem, "Duration", "duration", default="8"))

                    try:
                        anchor_x = int(float(raw_anchor[0]) * self.scale)
                        anchor_y = int(float(raw_anchor[1]) * self.scale)
                        vel_x    = float(raw_vel[0]) * self.scale
                        vel_y    = float(raw_vel[1]) * self.scale
                    except (ValueError, IndexError):
                        anchor_x = anchor_y = 0
                        vel_x = vel_y = 0.0

                    pm = self._load_pixmap(img_name)
                    if pm:
                        poses.append(Pose(pm, anchor_x, anchor_y, vel_x, vel_y, duration))
                    else:
                        print(f"[SpriteEngine] ⚠ Image introuvable : '{img_name}' (action={name})")

            if poses:
                self.actions[name] = ActionDef(
                    name=name,
                    action_type=action_type,
                    border_type=border_type,
                    poses=poses,
                    loop=loop,
                    gravity=gravity_val,
                    resistance_x=resistance_x,
                    resistance_y=resistance_y,
                    velocity_param=velocity_param,
                    ie_offset_x=ie_offset_x,
                    ie_offset_y=ie_offset_y,
                    throw_initial_vx=throw_initial_vx,
                    throw_gravity=throw_gravity,
                )
            # Actions Embedded sans poses → ignorer silencieusement

        loaded = len(self.actions)
        print(f"[SpriteEngine] {loaded} actions chargées pour {self.path.name}")
        if loaded > 0:
            print(f"[SpriteEngine] Actions disponibles : {list(self.actions.keys())}")

        if loaded == 0:
            print("[SpriteEngine] Aucune action valide → fallback")
            self._create_fallback_action()

    def _create_fallback_action(self) -> None:
        """Utilise le premier PNG disponible comme sprite statique."""
        png = None
        for d in self._img_dirs:
            pngs = sorted(d.glob("*.png"))
            if pngs:
                png = pngs[0]
                break

        if png is None:
            print("[SpriteEngine] ⚠ Aucun PNG trouvé dans les dossiers images !")
            return

        print(f"[SpriteEngine] Fallback sur : {png}")
        pm = QPixmap(str(png))
        if pm.isNull():
            return

        if self.scale != 1.0:
            pm = pm.scaled(
                int(pm.width() * self.scale),
                int(pm.height() * self.scale),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        pose = Pose(pm, pm.width() // 2, pm.height(), 0.0, 0.0, 30)
        self.actions["Stand"] = ActionDef("Stand", "Stay", "Floor", [pose])
        print(f"[SpriteEngine] Action fallback 'Stand' créée ({pm.width()}x{pm.height()}px)")

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def get_action(self, name: str) -> Optional[ActionDef]:
        return self.actions.get(name)

    def action_names(self) -> list[str]:
        return list(self.actions.keys())

    def has_action(self, name: str) -> bool:
        return name in self.actions

    def flip_pixmap(self, pm: QPixmap) -> QPixmap:
        """Retourne la version miroir horizontal d'un pixmap (avec cache stable)."""
        key = f"__flip__{pm.cacheKey()}"
        if key not in self._pixmap_cache:
            self._pixmap_cache[key] = pm.transformed(QTransform().scale(-1, 1))
        return self._pixmap_cache[key]


class AnimationPlayer:
    def __init__(self, action: ActionDef):
        self.action   = action
        self._pose_idx  = 0
        self._tick_count = 0
        self.finished   = False

    def reset(self, action: ActionDef) -> None:
        self.action      = action
        self._pose_idx   = 0
        self._tick_count = 0
        self.finished    = False

    def tick(self) -> Pose:
        pose = self.current_pose()
        self._tick_count += 1
        if self._tick_count >= pose.duration:
            self._tick_count = 0
            self._pose_idx += 1
            if self._pose_idx >= len(self.action.poses):
                if self.action.loop:
                    self._pose_idx = 0
                else:
                    self._pose_idx = len(self.action.poses) - 1
                    self.finished  = True
        return pose

    def current_pose(self) -> Pose:
        return self.action.poses[self._pose_idx]