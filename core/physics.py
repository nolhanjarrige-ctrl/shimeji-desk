"""core/physics.py
Moteur physique FIDÈLE à Shimeji-ee.

Principe fondamental (extrait du source Java Shimeji-ee) :
  - feet_x, feet_y = position de l'ANCHOR dans les coordonnées écran
  - screen_x = feet_x - anchor_x_in_sprite
  - screen_y = feet_y - anchor_y_in_sprite
  - Détection surface : abs(feet_y - surface_y) <= TOLERANCE (5px)
  - Mouvement : feet += pose.velocity  (la velocity de la pose est LE mouvement)
  - Gravité : uniquement en chute libre (pas en contact avec une surface)
  - GRAVITY = 3.5 (valeur réelle de l'XML Amiya)
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRect

if TYPE_CHECKING:
    from core.window_detector import WindowDetector
    from core.behavior import State


# ── Constantes Shimeji-ee ────────────────────────────────────────────
GRAVITY        = 3.5    # px/tick²
MAX_FALL_VY    = 32.0   # px/tick (cap)
SURFACE_TOL    = 5      # px — tolérance isOn() Shimeji
WALL_TOL       = 5      # px — tolérance contact mur


@dataclass
class PhysicsState:
    # Anchor position (= point de contact avec la surface)
    feet_x: float = 400.0
    feet_y: float = 800.0

    # Vitesse de chute + lancer
    fall_vy:      float = 0.0
    fall_vx:      float = 0.0   # vitesse horizontale lancer
    # Physique personnalisée depuis XML Falling
    gravity:      float = 3.5
    resistance_x: float = 0.05
    resistance_y: float = 0.1

    # Saut directionnel Shimeji
    jump_target_x:   float = 0.0
    jump_target_y:   float = 0.0
    jump_velocity:   float = 35.0
    jump_active:     bool  = False
    jump_vx:         float = 0.0
    jump_vy:         float = 0.0

    # WalkWithIE : fenêtre Win32 portée
    held_hwnd:       int   = 0      # HWND de la fenêtre portée (0 = aucune)
    held_win_x:      int   = 0      # position X de la fenêtre quand saisie
    held_win_y:      int   = 0      # position Y de la fenêtre quand saisie
    held_win_w:      int   = 0      # largeur de la fenêtre portée
    held_win_h:      int   = 0      # hauteur de la fenêtre portée
    held_prev_feet_x: float = 0.0  # feet_x au tick précédent (calcul delta)
    ie_offset_x:     int   = 0      # IeOffsetX du XML
    ie_offset_y:     int   = -36    # IeOffsetY du XML

    # ThrowIE : fenêtre lancée (physique indépendante)
    throw_active:    bool  = False
    throw_hwnd:      int   = 0
    throw_win_x:     float = 0.0
    throw_win_y:     float = 0.0
    throw_vx:        float = 45.0
    throw_vy:        float = 0.0
    throw_gravity:   float = 0.1

    # Surfaces de contact
    on_floor:      bool = True
    on_wall_left:  bool = False
    on_wall_right: bool = False
    on_ceiling:    bool = False
    on_ie_floor:   bool = False   # dessus d'une fenêtre
    on_ie_ceiling: bool = False   # dessous d'une fenêtre

    # Direction du regard (gérée par behavior, stockée ici pour render)
    look_right: bool = True

    # ── Propriétés dérivées ──────────────────────────────────────────

    @property
    def on_any_floor(self) -> bool:
        return self.on_floor or self.on_ie_floor

    @property
    def on_any_ceiling(self) -> bool:
        return self.on_ceiling or self.on_ie_ceiling

    @property
    def on_any_wall(self) -> bool:
        return self.on_wall_left or self.on_wall_right

    @property
    def on_any_surface(self) -> bool:
        return self.on_any_floor or self.on_any_ceiling or self.on_any_wall

    @property
    def at_left_edge(self) -> bool:
        return self.on_wall_left

    @property
    def at_right_edge(self) -> bool:
        return self.on_wall_right


class PhysicsEngine:
    """
    Physique Shimeji-ee exacte.

    Surfaces :
      FLOOR   → bas WorkArea  ou dessus d'une fenêtre visible
      WALL    → bords latéraux WorkArea ou bords d'une fenêtre visible
      CEILING → haut WorkArea ou dessous d'une fenêtre visible
    """

    def __init__(self, monitor_manager, window_detector: "WindowDetector",
                 walk_speed: float = 1.0, gravity: float = GRAVITY):
        self.wd      = window_detector
        self.GRAVITY = gravity
        self.state   = PhysicsState()
        self.other_mascots: list["PhysicsEngine"] = []

    # ── Helpers écran ─────────────────────────────────────────────────

    def _screen(self, x: int, y: int) -> QRect:
        for s in QApplication.screens():
            g = s.geometry()
            if g.left() <= x <= g.right() and g.top() <= y <= g.bottom():
                return g
        # Fallback: trouver l'écran le plus proche (gestion DPI multi-écran)
        best = QApplication.primaryScreen().geometry()
        best_dist = float('inf')
        for s in QApplication.screens():
            g = s.geometry()
            cx = max(g.left(), min(x, g.right()))
            cy = max(g.top(), min(y, g.bottom()))
            dist = abs(x-cx) + abs(y-cy)
            if dist < best_dist:
                best_dist = dist
                best = g
        return best

    def _workarea(self, x: int, y: int):
        """Retourne (left, top, right, bottom) du moniteur courant."""
        g = self._screen(x, y)
        return g.left(), g.top(), g.right(), g.bottom()

    # ── Téléportation ─────────────────────────────────────────────────

    def teleport(self, feet_x: float, feet_y: float) -> None:
        s = self.state
        s.feet_x = feet_x
        s.feet_y = feet_y
        s.fall_vy = 0.0
        s.on_floor = False
        s.on_ie_floor = False

    # ── Tick principal ────────────────────────────────────────────────

    def tick(self,
             behavior_state: "State",
             pose_vx: float,  # velocity déjà signée (gauche native → flip appliqué avant)
             pose_vy: float,
             sprite_w: int,
             sprite_h: int,
             anchor_x: int,   # pixel de l'anchor dans le sprite (après flip éventuel)
             anchor_y: int,
             ) -> PhysicsState:

        from core.behavior import State

        s  = self.state
        ix = int(s.feet_x)
        iy = int(s.feet_y)

        # ── DRAG : géré entièrement par mascot_window ─────────────────
        if behavior_state in (State.DRAG, State.RESISTING):
            s.fall_vy = 0.0
            s.fall_vx = 0.0
            s.on_floor = s.on_ie_floor = False
            s.on_wall_left = s.on_wall_right = False
            s.on_ceiling = s.on_ie_ceiling = False
            return s

        # ── Traversée multi-écran ─────────────────────────────────────
        self._handle_screen_cross(s, sprite_w, anchor_x)
        ix = int(s.feet_x)
        iy = int(s.feet_y)

        left, top, right, bottom = self._workarea(ix, iy)

        # ── Surfaces disponibles ──────────────────────────────────────
        floor_y    = self._find_floor_y(ix, iy, top, bottom)
        ceiling_y  = self._find_ceiling_y(ix, iy, top, bottom)

        # ── Application par état ──────────────────────────────────────

        if behavior_state in (State.WALK_LEFT, State.WALK_RIGHT,
                               State.RUN_LEFT, State.RUN_RIGHT,
                               State.STAND, State.SIT, State.SLEEP,
                               State.BUSY, State.FALL,
                               State.BOUNCING,
                               State.WALK_WITH_IE, State.FALL_WITH_IE,
                               State.READY_THROW, State.THROW_IE):
            self._tick_floor(s, pose_vx, pose_vy,
                             sprite_w, anchor_x,
                             left, right, floor_y, ceiling_y, bottom)

        elif behavior_state == State.JUMPING:
            if s.jump_active:
                self._tick_jump(s, left, top, right, bottom)
            else:
                # Pas de cible → chute libre normale (fallback)
                self._tick_floor(s, 0.0, 0.0,
                                 sprite_w, anchor_x,
                                 left, right, floor_y, ceiling_y, bottom)

        elif behavior_state in (State.GRAB_WALL, State.CLIMB_WALL):
            self._tick_wall(s, pose_vx, pose_vy,
                            sprite_w, anchor_x,
                            left, top, right, bottom,
                            anchor_y=anchor_y)

        elif behavior_state in (State.GRAB_CEILING, State.CLIMB_CEILING):
            self._tick_ceiling(s, pose_vx, pose_vy,
                               sprite_w, anchor_x,
                               ceiling_y, left, right,
                               top=top, bottom=bottom,
                               anchor_y=anchor_y)

        else:
            # Fallback : gravité simple
            self._apply_gravity(s, floor_y)

        return s

    # ──────────────────────────────────────────────────────────────────
    # FLOOR
    # ──────────────────────────────────────────────────────────────────

    def _tick_jump(self, s, left: int, top: int, right: int, bottom: int):
        """
        Jump action Shimeji-ee — mouvement LINÉAIRE à vitesse constante.
        Pas de gravité, pas de résistance : le perso glisse en ligne droite
        vers (jump_target_x, jump_target_y) à jump_velocity px/tick.
        Contact mur/sol/plafond détecté à chaque tick.
        """

        vel = s.jump_velocity
        dx = s.jump_target_x - s.feet_x
        dy = s.jump_target_y - s.feet_y
        dist = math.sqrt(dx * dx + dy * dy)

        # Reset surfaces
        s.on_floor = s.on_ie_floor = False
        s.on_wall_left = s.on_wall_right = False
        s.on_ceiling = s.on_ie_ceiling = False

        if dist <= vel:
            # Mémoriser la direction juste avant l'arrivée (pour flip)
            if dist > 0.1:
                s.jump_vx = vel * dx / dist
                s.jump_vy = vel * dy / dist
            # Arrivée à destination
            s.feet_x = s.jump_target_x
            s.feet_y = s.jump_target_y
            s.jump_active = False
            # Détecter quelle surface on a atteinte
            s.on_wall_left  = abs(s.feet_x - left)  <= WALL_TOL
            s.on_wall_right = abs(s.feet_x - right) <= WALL_TOL
            # Sol WorkArea
            s.on_floor = abs(s.feet_y - bottom) <= SURFACE_TOL and not s.on_any_wall
            # Sol IE (atterrissage sur le dessus d'une fenêtre)
            if not s.on_floor and not s.on_any_wall:
                try:
                    ie_y = self.wd.get_floor_at(int(s.feet_x), int(s.feet_y), 0, bottom)
                    s.on_ie_floor = ie_y is not None and abs(s.feet_y - ie_y) <= SURFACE_TOL * 2
                except Exception:
                    s.on_ie_floor = False
            else:
                s.on_ie_floor = False
            # Plafond écran
            s.on_ceiling = (not s.on_any_floor and not s.on_any_wall
                            and s.feet_y <= top + 128)
            # Plafond IE = vérifier qu'une fenêtre est réellement présente
            if (not s.on_any_floor and not s.on_any_wall and not s.on_ceiling
                    and 100 < s.feet_y < bottom - 30):
                try:
                    ie_c = self.wd.get_ceiling_at(int(s.feet_x), int(s.feet_y), top, bottom)
                    s.on_ie_ceiling = ie_c is not None and ie_c > top
                except Exception:
                    s.on_ie_ceiling = False
            else:
                s.on_ie_ceiling = False
        else:
            # Avancer vers la cible à vitesse constante
            s.feet_x += vel * dx / dist
            s.feet_y += vel * dy / dist
            # Mettre à jour direction pour flip visuel
            s.jump_vx = vel * dx / dist
            s.jump_vy = vel * dy / dist
            # Contact mur WorkArea en cours de vol
            if s.feet_x <= float(left):
                s.feet_x = float(left); s.on_wall_left  = True; s.jump_active = False
            elif s.feet_x >= float(right):
                s.feet_x = float(right); s.on_wall_right = True; s.jump_active = False
            # Contact sol en cours de vol
            if s.feet_y >= float(bottom):
                s.feet_y = float(bottom); s.on_floor = True; s.jump_active = False
            # Contact plafond WorkArea
            if s.feet_y <= float(top) + 64 and not s.jump_active:
                s.feet_y = float(top) + 64; s.on_ceiling = True

        s.fall_vy = 0.0
        s.fall_vx = 0.0

    def _tick_floor(self, s, pose_vx, pose_vy,
                    sprite_w, anchor_x,
                    left, right, floor_y, ceiling_y, screen_bottom):

        # 1. Mouvement horizontal
        prev_x = s.feet_x
        s.feet_x += pose_vx

        # 2. Détection murs (WorkArea + IE) — une seule passe
        # Anti-tunnel : tester aussi les points intermédiaires si vx est grand
        s.on_wall_left  = False
        s.on_wall_right = False

        if abs(pose_vx) > 0.1:
            steps = max(1, int(abs(pose_vx) / 2))
            for i in range(1, steps + 2):
                test_x = prev_x + pose_vx * min(i, steps) / steps
                # Mur WorkArea
                if test_x <= left + WALL_TOL:
                    s.feet_x = float(left)
                    s.on_wall_left = True
                    break
                if test_x >= right - WALL_TOL:
                    s.feet_x = float(right)
                    s.on_wall_right = True
                    break
                # Mur IE — seulement si le perso est dans la hauteur de la fenêtre
                # (pas sur son dessus : y > top + TOL)
                # Si y == window.top (on_ie_floor), les bords latéraux ne bloquent pas
                try:
                    ie_lw, ie_rw = self.wd.get_wall_at(int(test_x), int(s.feet_y),
                                                        tolerance=WALL_TOL)
                    if ie_lw is not None and pose_vx < 0:
                        s.feet_x = float(ie_lw)
                        s.on_wall_left = True
                        break
                    elif ie_rw is not None and pose_vx > 0:
                        s.feet_x = float(ie_rw)
                        s.on_wall_right = True
                        break
                except Exception:
                    pass
        else:
            s.on_wall_left  = s.feet_x <= left  + WALL_TOL
            s.on_wall_right = s.feet_x >= right - WALL_TOL

        # Clamp final
        s.feet_x = max(float(left), min(float(right), s.feet_x))

        # 3. Gravité / sol
        # Si fall_vx actif → forcer la chute même si au sol (lancer depuis le sol)
        if s.on_any_floor and abs(s.fall_vx) < 0.2 and s.fall_vy >= 0:
            # Vérifier que le sol est encore proche avant de snapper
            # Si floor_y a beaucoup changé (marché hors d'une IE), on tombe plutôt
            if abs(floor_y - s.feet_y) <= SURFACE_TOL * 3:
                s.feet_y  = floor_y
                s.fall_vy = 0.0
                s.on_floor    = abs(floor_y - screen_bottom) <= SURFACE_TOL
                s.on_ie_floor = not s.on_floor
                # Vérifier si le sol a disparu sous nos pieds (sortie de IE)
                if not self._is_valid_floor(int(s.feet_x), int(s.feet_y),
                                            floor_y, screen_bottom):
                    s.on_floor    = False
                    s.on_ie_floor = False
            else:
                # Sol trop loin (marché hors d'une IE) → chute libre depuis position actuelle
                s.on_floor    = False
                s.on_ie_floor = False
        else:
            # Chute libre — physique Shimeji : RegistanceX/Y + Gravity personnalisés
            grav   = s.gravity        # Gravity de l'action Falling
            res_x  = s.resistance_x   # RegistanceX (drag horizontal)
            res_y  = s.resistance_y   # RegistanceY (drag vertical)

            # Mouvement horizontal avec résistance air
            if abs(s.fall_vx) > 0.2:
                s.feet_x += s.fall_vx
                # Si on touche un bord WorkArea → arrêter vx (le behavior va GRAB_WALL)
                if s.feet_x <= float(left):
                    s.feet_x    = float(left)
                    s.fall_vx   = 0.0
                    s.on_wall_left  = True
                    s.on_wall_right = False
                elif s.feet_x >= float(right):
                    s.feet_x    = float(right)
                    s.fall_vx   = 0.0
                    s.on_wall_left  = False
                    s.on_wall_right = True
                else:
                    # Vérifier les murs de fenêtres IE pendant la chute
                    try:
                        ie_lw, ie_rw = self.wd.get_wall_at(int(s.feet_x), int(s.feet_y))
                        if ie_lw is not None and s.fall_vx < 0:
                            s.feet_x = float(ie_lw); s.fall_vx = 0.0
                            s.on_wall_left = True; s.on_wall_right = False
                        elif ie_rw is not None and s.fall_vx > 0:
                            s.feet_x = float(ie_rw); s.fall_vx = 0.0
                            s.on_wall_left = False; s.on_wall_right = True
                        else:
                            s.fall_vx *= (1.0 - res_x)
                    except Exception:
                        s.fall_vx *= (1.0 - res_x)
            else:
                s.fall_vx = 0.0

            # Gravité avec résistance verticale
            s.fall_vy = (s.fall_vy + grav) * (1.0 - res_y)
            s.fall_vy = min(s.fall_vy, MAX_FALL_VY)

            new_y = s.feet_y + s.fall_vy

            # Anti-tunnel : si fall_vy est grand, vérifier aussi le sol à la position
            # projetée — empêche le perso de traverser une fenêtre en un tick
            if s.fall_vy > SURFACE_TOL and new_y > s.feet_y:
                # Utiliser left/right pour retrouver le top de l'écran courant
                _, proj_top, _, _ = self._workarea(int(s.feet_x), int(new_y))
                proj_floor = self._find_floor_y(int(s.feet_x), int(new_y),
                                                proj_top, screen_bottom)
                if proj_floor < floor_y:
                    floor_y = proj_floor

            if new_y >= floor_y:
                s.feet_y      = floor_y
                s.fall_vy     = 0.0
                s.fall_vx     = 0.0
                s.on_floor    = abs(floor_y - screen_bottom) <= SURFACE_TOL
                s.on_ie_floor = not s.on_floor
            else:
                s.feet_y      = new_y
                s.on_floor    = False
                s.on_ie_floor = False

        s.on_ceiling    = False
        s.on_ie_ceiling = False

    def _is_valid_floor(self, x: int, y: int, floor_y: float,
                        screen_bottom: int) -> bool:
        """Vérifie que le perso est toujours sur son sol (WorkArea ou fenêtre)."""
        if abs(y - screen_bottom) <= SURFACE_TOL:
            return True
        try:
            ie_y = self.wd.get_floor_at(x, y, 0, screen_bottom)
            if ie_y is not None and abs(y - ie_y) <= SURFACE_TOL:
                return True
        except Exception:
            pass
        return False

    # ──────────────────────────────────────────────────────────────────
    # WALL
    # ──────────────────────────────────────────────────────────────────

    def _tick_wall(self, s, pose_vx, pose_vy,
                   sprite_w, anchor_x,
                   left, top, right, bottom,
                   anchor_y: int = 128):
        """
        Sur le mur :
          - feet_x = bord du mur (exactement)
          - feet_y bouge via pose_vy (montée/descente)
          - Pas de gravité
          - Quand atteint le bas → revenir au sol
          - Quand atteint le haut (ou dessous d'une fenêtre) → transition ceiling
        """
        # Snap au mur — conserver le mur sur lequel on est déjà
        # Seulement recalculer si on n'est sur aucun mur (premier tick)
        if not s.on_wall_left and not s.on_wall_right:
            dist_left  = abs(s.feet_x - left)
            dist_right = abs(s.feet_x - right)
            if dist_left <= dist_right:
                s.on_wall_left  = True
                s.on_wall_right = False
            else:
                s.on_wall_left  = False
                s.on_wall_right = True

        if s.on_wall_left:
            s.feet_x = float(left)
        else:
            s.feet_x = float(right)

        # Mouvement vertical via velocity
        s.feet_y += pose_vy
        s.fall_vy = 0.0

        # Chercher la surface plafond la plus proche (plafond écran ou bas d'une fenêtre)
        # On cherche dans la zone [top, feet_y] pour trouver un plafond IE au-dessus
        ceiling_y = self._find_ceiling_y(int(s.feet_x), int(s.feet_y), top, bottom)
        if ceiling_y is None:
            ceiling_y = top

        # Limite haute : clamp au plafond effectif + 64 (Shimeji ClimbAlongWall)
        clamp_top = ceiling_y + 64
        clamp_top = max(top, min(clamp_top, bottom - 64))

        # Limites verticales
        if s.feet_y >= bottom:
            s.feet_y = float(bottom)
        elif s.feet_y <= clamp_top:
            s.feet_y = float(clamp_top)

        # Surfaces
        s.on_floor      = abs(s.feet_y - bottom) <= SURFACE_TOL
        s.on_ie_floor   = False
        # on_ceiling = True quand feet_y a atteint la limite haute (plafond écran ou IE)
        s.on_ceiling    = s.feet_y <= clamp_top + SURFACE_TOL
        s.on_ie_ceiling = s.on_ceiling and (ceiling_y > top)  # True si c'est un IE ceiling

    # ──────────────────────────────────────────────────────────────────
    # CEILING
    # ──────────────────────────────────────────────────────────────────

    def _tick_ceiling(self, s, pose_vx, pose_vy,
                      sprite_w, anchor_x,
                      ceiling_y, left, right,
                      top: int = 0, bottom: int = 1080, anchor_y: int = 39):
        """
        Au plafond :
          - feet_y = ceiling_y (exactement)
          - feet_x bouge via pose_vx (horizontal)
          - Pas de gravité
        """
        if ceiling_y is None:
            # Pas de plafond → tomber
            s.on_ceiling    = False
            s.on_ie_ceiling = False
            return

        # Shimeji exact : feet_y = ceiling_y
        s.feet_y = float(ceiling_y)

        # Mouvement horizontal — Shimeji utilise les bords WorkArea directement
        s.feet_x += pose_vx
        s.feet_x = max(float(left), min(s.feet_x, float(right)))

        s.fall_vy       = 0.0
        s.on_ceiling    = True
        s.on_floor      = False
        s.on_ie_floor   = False
        # Détecter coin plafond-mur : atteint le bord WorkArea
        s.on_wall_left  = s.feet_x <= float(left)  + WALL_TOL
        s.on_wall_right = s.feet_x >= float(right) - WALL_TOL

    # ──────────────────────────────────────────────────────────────────
    # Gravité simple
    # ──────────────────────────────────────────────────────────────────

    def _apply_gravity(self, s, floor_y: float) -> None:
        s.fall_vy = min(s.fall_vy + self.GRAVITY, MAX_FALL_VY)
        s.feet_y += s.fall_vy
        if s.feet_y >= floor_y:
            s.feet_y   = floor_y
            s.fall_vy  = 0.0
            s.on_floor = True
        else:
            s.on_floor = False

    # ──────────────────────────────────────────────────────────────────
    # Détection des surfaces
    # ──────────────────────────────────────────────────────────────────

    def _find_floor_y(self, x: int, y: int, top: int, bottom: int) -> float:
        """
        Retourne le Y du sol effectif sous les pieds.
        Méthode Shimeji : appelle get_floor_at chaque tick pour détecter la surface IE.
        NE modifie JAMAIS feet_y directement — le snap est géré par _tick_floor.
        """
        try:
            ie_y = self.wd.get_floor_at(x, y, top, bottom)
            if ie_y is not None and top <= ie_y <= bottom:
                return float(ie_y)
        except Exception:
            pass
        return float(bottom)

    def _find_ceiling_y(self, x: int, y: int, top: int, bottom: int) -> Optional[int]:
        """Plafond du moniteur courant uniquement."""
        # Le plafond = haut de l'écran courant (validé dans [top, bottom])
        best: Optional[int] = top

        # Dessous de fenêtres visibles (validé dans les limites de l'écran)
        try:
            ie_ceil = self.wd.get_ceiling_at(x, y, top, bottom)
            if ie_ceil is not None and top < ie_ceil < bottom:
                best = ie_ceil
        except Exception:
            pass

        return best

    # ──────────────────────────────────────────────────────────────────
    # Traversée multi-écran
    # ──────────────────────────────────────────────────────────────────

    def _handle_screen_cross(self, s, sprite_w: int, anchor_x: int) -> None:
        screens = [sc.geometry() for sc in QApplication.screens()]
        if len(screens) <= 1:
            return

        ix, iy  = int(s.feet_x), int(s.feet_y)
        g       = self._screen(ix, iy)
        left, top, right, bottom = g.left(), g.top(), g.right(), g.bottom()

        target = None; nx = None; ny = None

        if s.feet_x > right + 20:
            target = self._find_adjacent(screens, right, iy, "right")
            if target:
                nx = float(target.left())
                ny = self._map_y(iy, top, bottom, target.top(), target.bottom())
        elif s.feet_x < left - 20:
            target = self._find_adjacent(screens, left, iy, "left")
            if target:
                nx = float(target.right())
                ny = self._map_y(iy, top, bottom, target.top(), target.bottom())
        elif s.feet_y > bottom + 20:
            target = self._find_adjacent(screens, ix, bottom, "down")
            if target:
                nx = self._map_x(ix, left, right, target.left(), target.right())
                ny = float(target.top() + 5)
        elif s.feet_y < top - 20:
            target = self._find_adjacent(screens, ix, top, "up")
            if target:
                nx = self._map_x(ix, left, right, target.left(), target.right())
                ny = float(target.bottom() - 5)

        if target and nx is not None:
            s.feet_x   = nx
            s.feet_y   = ny
            s.on_floor = False
            s.fall_vy  = 0.0

    def _find_adjacent(self, screens, rx, ry, d):
        best = None; bd = float("inf")
        for g in screens:
            if d == "right":
                if g.left() < rx: continue
                if not (g.top()-50 <= ry <= g.bottom()+50): continue
                dist = g.left() - rx
            elif d == "left":
                if g.right() > rx: continue
                if not (g.top()-50 <= ry <= g.bottom()+50): continue
                dist = rx - g.right()
            elif d == "down":
                if g.top() < ry: continue
                if not (g.left()-50 <= rx <= g.right()+50): continue
                dist = g.top() - ry
            else:
                if g.bottom() > ry: continue
                if not (g.left()-50 <= rx <= g.right()+50): continue
                dist = ry - g.bottom()
            if dist < bd: bd = dist; best = g
        return best

    @staticmethod
    def _map_y(y, st, sb, dt, db):
        if sb == st: return float(dt)
        return float(dt + (y - st) / (sb - st) * (db - dt))

    @staticmethod
    def _map_x(x, sl, sr, dl, dr):
        if sr == sl: return float(dl)
        return float(dl + (x - sl) / (sr - sl) * (dr - dl))

    # ── Drag ─────────────────────────────────────────────────────────

    def set_drag_position(self, feet_x: float, feet_y: float) -> None:
        s = self.state
        s.feet_x   = feet_x
        s.feet_y   = feet_y
        s.fall_vy  = 0.0
        s.on_floor = False