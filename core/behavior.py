"""core/behavior.py — Fidèle à Shimeji-ee XML (Amiya/behaviors.xml)

Convention look_right (identique Shimeji-ee) :
  look_right=True  → sprite FLIPPÉ → va à DROITE
  look_right=False → sprite natif  → va à GAUCHE
"""
from __future__ import annotations
import random
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional


class State(Enum):
    STAND         = auto()
    WALK_LEFT     = auto()
    WALK_RIGHT    = auto()
    RUN_LEFT      = auto()
    RUN_RIGHT     = auto()
    SIT           = auto()
    SLEEP         = auto()
    BUSY          = auto()
    FALL          = auto()
    GRAB_WALL     = auto()
    CLIMB_WALL    = auto()
    GRAB_CEILING  = auto()
    CLIMB_CEILING = auto()
    DRAG          = auto()
    RESISTING     = auto()
    JUMPING       = auto()
    BOUNCING      = auto()
    TALKING       = auto()
    TELEPORT      = auto()
    WALK_WITH_IE  = auto()   # WalkWithIE / RunWithIE — marche en portant une fenêtre
    FALL_WITH_IE  = auto()   # FallWithIE — tombe en tenant la fenêtre
    READY_THROW   = auto()   # ReadyThrow — prépare le lancer
    THROW_IE      = auto()   # ThrowIE — lance la fenêtre


STATE_ACTION_MAP: dict[State, list[str]] = {
    State.STAND:         ["Stand"],
    State.WALK_LEFT:     ["Walk"],
    State.WALK_RIGHT:    ["Walk"],
    State.RUN_LEFT:      ["Run"],
    State.RUN_RIGHT:     ["Run"],
    State.SIT:           ["Sit"],
    State.SLEEP:         ["Snooze", "Rest"],
    State.BUSY:          ["Busy", "Deploy1"],
    State.FALL:          ["Falling", "Fall"],
    State.GRAB_WALL:     ["GrabWall",    "ClimbWall"],
    State.CLIMB_WALL:    ["ClimbWall",   "GrabWall"],
    State.GRAB_CEILING:  ["GrabCeiling", "ClimbCeiling"],
    State.CLIMB_CEILING: ["ClimbCeiling","GrabCeiling"],
    State.DRAG:          ["Pinched", "Dragged"],
    State.RESISTING:     ["Resisting"],
    State.JUMPING:       ["Jumping", "Falling"],
    State.BOUNCING:      ["Bouncing", "Deploy1", "DeployEnter"],
    State.TALKING:       ["Stand"],
    State.TELEPORT:      ["TeleportFromWall", "TeleportFromCeiling"],
    State.WALK_WITH_IE:  ["WalkWithIe", "RunWithIe"],
    State.FALL_WITH_IE:  ["FallWithIe"],
    State.READY_THROW:   ["ReadyThrow"],
    State.THROW_IE:      ["ThrowIe"],
}

TOL = 8  # px — tolérance "cible atteinte" (Shimeji SURFACE_TOL=5, on prend 8)


@dataclass
class Step:
    state:          State
    target_x:       Optional[float] = None
    target_y:       Optional[float] = None
    duration:       Optional[int]   = None
    offset_x:       Optional[float] = None
    offset_y:       Optional[float] = None
    do_look:        bool            = False
    look_right_val: Optional[bool]  = None
    teleport_floor: bool            = False
    jump_action:    Optional[str]   = None  # action XML à utiliser (Jumping/Jumping2/Jumping3)


class BehaviorEngine:

    def __init__(self, character_path: str, config=None):
        self.character_path      = Path(character_path)
        self._config             = config  # Config optionnelle pour les toggles
        self._state              = State.STAND
        self._look_right         = False
        self._available_actions: set[str] = set()
        self._steps:      list[Step] = []
        self._step_idx:   int        = 0
        self._step_ticks: int        = 0
        self._pending_offset_x: Optional[float] = None
        self._pending_offset_y: Optional[float] = None
        self._pending_teleport_floor: bool = False  # Faust : téléport instantané au sol
        self._L, self._T, self._R, self._B = 0, 0, 1920, 1080
        self._cursor_x: float = 960.0
        self._ie_ceiling_y: Optional[int] = None  # dessous de fenêtre visible
        self._ie_floor_y:   Optional[int] = None  # dessus de fenêtre visible au-dessus
        self._ie_visible:   bool = False           # au moins une IE visible
        self._feet_x_hint:  float = 0.0            # position pieds pour conditions
        self._feet_y_hint:  float = 0.0
        self._neighbor_x:   Optional[float] = None   # X du mascot voisin
        self._thrown: bool    = False  # True si le perso vient d'être lancé
        self._drag_ticks: int = 0     # ticks depuis le début du drag (→ Resisting)
        self._new_floor_sequence()

    # ── API ───────────────────────────────────────────────────────────

    def set_available_actions(self, actions: set[str]) -> None:
        self._available_actions = actions

    def _cfg(self, attr: str, default=True):
        """Lit un toggle de config, retourne default si config absente."""
        if self._config is None:
            return default
        return getattr(self._config, attr, default)

    def set_workarea(self, left: int, top: int, right: int, bottom: int) -> None:
        self._L, self._T, self._R, self._B = left, top, right, bottom

    def set_ie_ceiling_y(self, y: Optional[int]) -> None:
        """Signale la Y du plafond IE actuel (bas d'une fenêtre visible au-dessus)."""
        self._ie_ceiling_y: Optional[int] = y

    def set_ie_floor_y(self, y: Optional[int]) -> None:
        """Signale la Y du sol IE le plus proche AU-DESSUS du perso — cible JumpToTop."""
        self._ie_floor_y = y

    def set_ie_visible(self, visible: bool) -> None:
        """Signale si au moins une fenêtre IE est visible à l'écran."""
        self._ie_visible = visible

    def set_feet_hint(self, x: float, y: float) -> None:
        """Donne la position actuelle des pieds pour les conditions de comportement."""
        self._feet_x_hint = x
        self._feet_y_hint = y

    def set_neighbor_x(self, x: Optional[float]) -> None:
        """Signale la position X du mascot le plus proche (interactions multi-persos)."""
        self._neighbor_x = x

    def current_jump_target(self) -> tuple[Optional[float], Optional[float]]:
        """Retourne (target_x, target_y) du Step JUMPING courant, ou (None, None)."""
        if self._steps and 0 <= self._step_idx < len(self._steps):
            s = self._steps[self._step_idx]
            if s.state == State.JUMPING:
                return s.target_x, s.target_y
        return None, None

    def current_jump_action(self) -> Optional[str]:
        """Retourne le nom de l'action saut à utiliser (Jumping/Jumping2/Jumping3)."""
        if self._steps and 0 <= self._step_idx < len(self._steps):
            s = self._steps[self._step_idx]
            if s.state == State.JUMPING:
                return s.jump_action
        return None

    def pop_jump_target_y(self) -> Optional[int]:
        """Compat legacy — retourne juste target_y."""
        _, ty = self.current_jump_target()
        return int(ty) if ty is not None else None

    @property
    def state(self) -> State:
        return self._state

    @property
    def look_right(self) -> bool:
        return self._look_right

    @look_right.setter
    def look_right(self, value: bool) -> None:
        self._look_right = value

    def set_cursor(self, x: float, y: float) -> None:
        self._cursor_x = x

    def pop_offset_x(self) -> Optional[float]:
        v = self._pending_offset_x; self._pending_offset_x = None; return v

    def pop_offset_y(self) -> Optional[float]:
        v = self._pending_offset_y; self._pending_offset_y = None; return v

    def pop_teleport_floor(self) -> bool:
        """Retourne True si le perso doit être téléporté instantanément au sol (Faust)."""
        v = self._pending_teleport_floor
        self._pending_teleport_floor = False
        return v

    def force_state(self, state: State) -> None:
        self._state = state; self._steps = []; self._step_idx = 0

    def notify_grabbed(self) -> None:
        self._drag_ticks = 0
        self.force_state(State.DRAG)

    def notify_released(self) -> None:
        self._thrown = True
        self.force_state(State.FALL)

    def notify_talking(self, talking: bool) -> None:
        self.force_state(State.TALKING if talking else State.STAND)

    def land(self) -> None:
        self._thrown = False
        self._new_floor_sequence()

    # ── Tick ──────────────────────────────────────────────────────────

    def tick(self, feet_x: float, feet_y: float,
             on_floor: bool, at_left_edge: bool = False,
             at_right_edge: bool = False, on_wall: bool = False,
             on_ceiling: bool = False, on_ie_top: bool = False, **_) -> State:

        if self._state == State.TALKING:
            return self._state

        if self._state in (State.DRAG, State.RESISTING):
            self._drag_ticks += 1
            # Resisting après ~150 ticks (5s à 30fps) comme Shimeji
            if (self._state == State.DRAG and self._drag_ticks > 150
                    and self._has(State.RESISTING)):
                self._state = State.RESISTING
            return self._state

        if self._state in (State.FALL, State.JUMPING):
            # Accrochage mur : après lancer OU après saut volontaire vers le mur
            if on_wall and self._has(State.GRAB_WALL):
                self._thrown = False
                self._look_right = not at_left_edge
                self._start([Step(State.GRAB_WALL, duration=int(20 + 60 * random.random()))])
                return self._state
            if on_ceiling and self._has(State.GRAB_CEILING):
                # Accrochage plafond après JumpToTop
                self._thrown = False
                self._start([Step(State.GRAB_CEILING, duration=int(20 + 60 * random.random()))])
                return self._state
            if on_floor or on_ie_top:
                self.land()
            return self._state

        if self._state == State.BOUNCING:
            # Bouncing = animation d'atterrissage one-shot
            # Sécurité: si on n'est plus au sol, tomber
            if not (on_floor or on_ie_top):
                self._state = State.FALL
            return self._state

        if self._state == State.TELEPORT:
            # TeleportFromWall : on laisse l'animation se jouer (durée gérée par _steps)
            pass  # géré via les Steps normalement

        if self._state in (State.WALK_WITH_IE, State.READY_THROW):
            # Marche avec fenêtre : sol requis, sinon lâcher et tomber
            if not (on_floor or on_ie_top):
                self.force_state(State.FALL)
                return self._state

        if self._state == State.FALL_WITH_IE:
            if on_floor or on_ie_top:
                self.land()
            return self._state

        self._step_ticks += 1

        if not self._steps or self._step_idx >= len(self._steps):
            self._choose_next(on_floor, on_ie_top, on_wall, on_ceiling)
            return self._state

        step = self._steps[self._step_idx]
        if self._step_done(step, feet_x, feet_y):
            self._advance()

        return self._state

    # ── Step completion ───────────────────────────────────────────────

    def _step_done(self, s: Step, fx: float, fy: float) -> bool:
        if s.duration is not None:
            return self._step_ticks >= s.duration

        # Instantanés
        if s.offset_x is not None or s.offset_y is not None:
            return True
        if s.do_look:
            return True
        if s.look_right_val is not None:
            return True

        # Cible X
        if s.target_x is not None:
            tx = s.target_x
            if s.state in (State.WALK_LEFT, State.RUN_LEFT):
                return fx <= tx + TOL
            if s.state in (State.WALK_RIGHT, State.RUN_RIGHT):
                return fx >= tx - TOL
            if s.state in (State.CLIMB_CEILING, State.GRAB_CEILING):
                # look_right=True → going RIGHT → fx croît
                # look_right=False → going LEFT  → fx décroît
                if self._look_right:
                    return fx >= tx - TOL
                else:
                    return fx <= tx + TOL
            return abs(fx - tx) <= TOL

        # Cible Y (mur monte → fy décroît)
        if s.target_y is not None:
            ty = s.target_y
            if s.state in (State.CLIMB_WALL, State.GRAB_WALL):
                return fy <= ty + TOL
            return fy >= ty - TOL

        return False

    def _advance(self) -> None:
        self._step_idx  += 1
        self._step_ticks = 0
        if self._step_idx >= len(self._steps):
            self._choose_next_from_last()
            return
        self._apply_step(self._steps[self._step_idx])

    def _apply_step(self, s: Step) -> None:
        # Offset X (instantané)
        if s.offset_x is not None:
            self._pending_offset_x = s.offset_x
            self._step_idx += 1; self._step_ticks = 0
            if self._step_idx < len(self._steps):
                self._apply_step(self._steps[self._step_idx])
            return

        # Offset Y (instantané)
        if s.offset_y is not None:
            self._pending_offset_y = s.offset_y
            self._step_idx += 1; self._step_ticks = 0
            if self._step_idx < len(self._steps):
                self._apply_step(self._steps[self._step_idx])
            return

        # Téléport au sol (Faust, instantané)
        if s.teleport_floor:
            self._pending_teleport_floor = True
            self._step_idx += 1; self._step_ticks = 0
            if self._step_idx < len(self._steps):
                self._apply_step(self._steps[self._step_idx])
            return

        # Look (inverse look_right)
        if s.do_look:
            self._look_right = not self._look_right
            self._step_idx += 1; self._step_ticks = 0
            if self._step_idx < len(self._steps):
                self._apply_step(self._steps[self._step_idx])
            return

        # Look LookRight="val"
        if s.look_right_val is not None:
            self._look_right = s.look_right_val
            self._step_idx += 1; self._step_ticks = 0
            if self._step_idx < len(self._steps):
                self._apply_step(self._steps[self._step_idx])
            return

        # Action normale
        self._state = s.state
        if s.state in (State.WALK_LEFT, State.RUN_LEFT):
            self._look_right = False
        elif s.state in (State.WALK_RIGHT, State.RUN_RIGHT):
            self._look_right = True
        elif s.state in (State.CLIMB_CEILING, State.GRAB_CEILING):
            if s.look_right_val is not None:
                # Valeur explicite (ClimbAlongWall : définie après Look)
                self._look_right = s.look_right_val
            elif s.target_x is not None:
                # Heuristique pour ClimbAlongCeiling (target aléatoire)
                self._look_right = s.target_x > (self._L + self._R) / 2
        # CLIMB_WALL/GRAB_WALL : look_right inchangé (déterminé par l'approche)

    # ── Navigation ───────────────────────────────────────────────────

    def _choose_next_from_last(self) -> None:
        s = self._state
        if s in (State.CLIMB_CEILING, State.GRAB_CEILING):
            self._new_ceiling_sequence()
        elif s in (State.CLIMB_WALL, State.GRAB_WALL):
            self._new_wall_sequence()
        else:
            self._new_floor_sequence()

    def _choose_next(self, on_floor, on_ie, on_wall, on_ceil) -> None:
        if on_ceil:               self._new_ceiling_sequence()
        elif on_wall:             self._new_wall_sequence()
        elif on_ie and not on_floor:  self._new_ie_top_sequence()
        elif on_floor or on_ie:   self._new_floor_sequence()
        else:                     self._state = State.FALL

    def _has(self, *states: State) -> bool:
        if not self._available_actions:
            return False
        for st in states:
            if any(a in self._available_actions for a in STATE_ACTION_MAP.get(st, [])):
                return True
        return False

    def _start(self, steps: list[Step]) -> None:
        self._steps = steps; self._step_idx = 0; self._step_ticks = 0
        if steps:
            self._apply_step(steps[0])

    def _pick(self, options: list[tuple]) -> list[Step]:
        """options = [(weight, [Step,...]), ...]"""
        return random.choices([s for _, s in options],
                              weights=[w for w, _ in options], k=1)[0]

    # ── FLOOR ─────────────────────────────────────────────────────────

    def _new_floor_sequence(self) -> None:
        L, T, R, B = self._L, self._T, self._R, self._B
        W = R - L
        H = B - T
        opts = []

        # WalkAlongWorkAreaFloor
        tx = float(L + 64 + random.random() * max(0, W - 128))
        st = State.WALK_RIGHT if tx > (L+R)/2 else State.WALK_LEFT
        opts.append((100, [Step(st, target_x=tx)]))

        # RunAlongWorkAreaFloor
        tx2 = float(L + 64 + random.random() * max(0, W - 128))
        st2 = State.RUN_RIGHT if tx2 > (L+R)/2 else State.RUN_LEFT
        opts.append((100, [Step(st2, target_x=tx2)]))

        # WalkLeftAlongFloorAndSit
        if self._has(State.SIT):
            txl = float(L + 100 + random.random() * 300)
            opts.append((150, [
                Step(State.WALK_LEFT, target_x=txl),
                Step(State.STAND, duration=int(20+random.random()*20)),
                Step(State.STAND, look_right_val=True),
                Step(State.STAND, duration=int(20+random.random()*20)),
                Step(State.SIT,   duration=int(500+random.random()*1000)),
            ]))

        # WalkRightAlongFloorAndSit
        if self._has(State.SIT):
            txr = float(R - 100 - random.random() * 300)
            opts.append((150, [
                Step(State.WALK_RIGHT, target_x=txr),
                Step(State.STAND, duration=int(20+random.random()*20)),
                Step(State.STAND, look_right_val=False),
                Step(State.STAND, duration=int(20+random.random()*20)),
                Step(State.SIT,   duration=int(500+random.random()*1000)),
            ]))

        # StandUp (Frequency=150)
        opts.append((150, [Step(State.STAND, duration=int(300+random.random()*500))]))

        # SitDown (Frequency=150)
        if self._has(State.SIT):
            opts.append((150, [Step(State.SIT, duration=int(400+random.random()*600))]))

        # Sleep (Frequency=100)
        if self._has(State.SLEEP):
            opts.append((100, [
                Step(State.STAND, look_right_val=True),
                Step(State.SLEEP, duration=int(600+random.random()*800)),
            ]))

        # Rest/Cozy (Frequency=100)
        if 'Rest' in self._available_actions:
            opts.append((100, [Step(State.SLEEP, duration=int(400+random.random()*600))]))

        # Special/Busy (Frequency=100)
        if self._has(State.BUSY):
            opts.append((100, [Step(State.BUSY, duration=int(400+random.random()*600))]))

        # GrabWorkAreaBottomLeftWall (Walk, Frequency=100) — Shimeji exact
        if self._has(State.CLIMB_WALL):
            opts.append((100, [
                Step(State.WALK_LEFT,  target_x=float(L)),
                Step(State.GRAB_WALL,  duration=10),
            ]))

        # GrabWorkAreaBottomRightWall (Walk, Frequency=100)
        if self._has(State.CLIMB_WALL):
            opts.append((100, [
                Step(State.WALK_RIGHT, target_x=float(R)),
                Step(State.GRAB_WALL,  duration=10),
            ]))

        # WalkAndGrabBottomLeftWall (Run, Frequency=100)
        if self._has(State.CLIMB_WALL):
            opts.append((100, [
                Step(State.RUN_LEFT,   target_x=float(L)),
                Step(State.GRAB_WALL,  duration=10),
            ]))

        # WalkAndGrabBottomRightWall (Run, Frequency=100)
        if self._has(State.CLIMB_WALL):
            opts.append((100, [
                Step(State.RUN_RIGHT,  target_x=float(R)),
                Step(State.GRAB_WALL,  duration=10),
            ]))
        # JumpToRightWall — Conditions Shimeji exactes :
        # anchor.x < workArea.left + 400 AND anchor.y > workArea.bottom - H/4
        # (perso dans le quart bas ET à moins de 400px du mur gauche → saute vers droite)
        feet_x_now = self._feet_x_hint
        feet_y_now = self._feet_y_hint
        if self._cfg('enable_jump') and self._has(State.CLIMB_WALL):
            if feet_x_now < L + 400 and feet_y_now > B - H / 4:
                target_y_r = float(B - random.random() * (H / 4))
                opts.append((120, [
                    Step(State.JUMPING,    target_x=float(R), target_y=target_y_r),
                    Step(State.GRAB_WALL,  duration=int(30 + random.random() * 70)),
                    Step(State.CLIMB_WALL, target_y=float(B - 64)),
                ]))

        # JumpToLeftWall — Conditions Shimeji exactes :
        # anchor.x >= workArea.right - 400 AND anchor.y > workArea.bottom - H/4
        if self._cfg('enable_jump') and self._has(State.CLIMB_WALL):
            if feet_x_now >= R - 400 and feet_y_now > B - H / 4:
                target_y_l = float(B - random.random() * (H / 4))
                opts.append((120, [
                    Step(State.JUMPING,    target_x=float(L), target_y=target_y_l),
                    Step(State.GRAB_WALL,  duration=int(30 + random.random() * 70)),
                    Step(State.CLIMB_WALL, target_y=float(B - 64)),
                ]))

        # LookAtNeighbor — se tourner vers un perso voisin (interaction multi-persos)
        # Shimeji : les persos se "remarquent" quand ils sont proches sur le sol
        if self._neighbor_x is not None:
            dx_neighbor = self._neighbor_x - self._feet_x_hint
            if abs(dx_neighbor) < 400:  # voisin à moins de 400px
                # Se tourner vers lui, marcher un peu dans sa direction, puis s'arrêter
                look_toward = dx_neighbor > 0  # True = regarder à droite
                toward_state = State.WALK_RIGHT if look_toward else State.WALK_LEFT
                tx_toward = float(self._feet_x_hint + dx_neighbor * 0.5)
                tx_toward = max(float(L + 30), min(float(R - 30), tx_toward))
                opts.append((60, [
                    Step(State.STAND,   look_right_val=look_toward, duration=20),
                    Step(toward_state,  target_x=tx_toward),
                    Step(State.STAND,   look_right_val=look_toward, duration=int(30 + random.random() * 40)),
                ]))
        cx = max(float(self._L), min(float(self._R), self._cursor_x))
        if cx > (self._L + self._R) / 2:
            opts.append((60, [Step(State.RUN_RIGHT, target_x=cx)]))
        else:
            opts.append((60, [Step(State.RUN_LEFT, target_x=cx)]))

        # JumpToTop — Shimeji: Jumping(TargetX=ie_x, TargetY=ie_bottom) → GrabCeiling
        # Utilise Jumping3 (vel=60) si disponible, comme dans behaviors.xml FrostNova
        if self._cfg('enable_jump') and self._ie_floor_y is not None and self._has(State.JUMPING):
            dh = self._B - self._ie_floor_y
            if 30 < dh <= 700:
                ie_target_x = float((self._L + self._R) // 2)
                # Choisir la bonne action : Jumping3 si dispo (vel=60), sinon Jumping (vel=35)
                jump_act = 'Jumping3' if 'Jumping3' in self._available_actions else None
                opts.append((80, [
                    Step(State.STAND,        duration=5),
                    Step(State.JUMPING,      target_x=ie_target_x,
                                             target_y=float(self._ie_floor_y),
                                             jump_action=jump_act),
                    Step(State.GRAB_CEILING, duration=int(20 + random.random() * 60)),
                ]))

        # JumpOnIEWall — sauter sur le bord de la fenêtre IE (depuis le sol)
        # Shimeji: Frequency=50, seulement si IE visible et perso à côté
        # Jumping2 (vel=25) pour un saut plus lent vers le mur IE
        if self._cfg('enable_jump') and self._ie_visible and self._has(State.JUMPING):
            jump_ie_act = 'Jumping2' if 'Jumping2' in self._available_actions else None
            # Sauter vers le mur gauche de l'IE (depuis la gauche)
            if feet_x_now < (self._L + self._R) / 2:
                ie_wall_target_y = float(B - random.random() * (H / 4))
                opts.append((50, [
                    Step(State.JUMPING,   target_x=float(L),
                                          target_y=ie_wall_target_y,
                                          jump_action=jump_ie_act),
                    Step(State.GRAB_WALL, duration=int(20 + random.random() * 40)),
                ]))
            else:
                ie_wall_target_y = float(B - random.random() * (H / 4))
                opts.append((50, [
                    Step(State.JUMPING,   target_x=float(R),
                                          target_y=ie_wall_target_y,
                                          jump_action=jump_ie_act),
                    Step(State.GRAB_WALL, duration=int(20 + random.random() * 40)),
                ]))

        # WalkWithIE / RunWithIe
        if self._cfg('enable_walk_with_ie') and self._ie_visible and self._has(State.WALK_WITH_IE):
            tx_wie = float(L + 100 + random.random() * max(0, W - 200))
            opts.append((80, [
                Step(State.WALK_WITH_IE, target_x=tx_wie),   # marche vers target_x
                Step(State.STAND, duration=20),
            ]))

            if self._has(State.THROW_IE) and self._ie_floor_y is not None:
                tx_throw = float(L + 100 + random.random() * max(0, W - 200))
                opts.append((40, [
                    Step(State.WALK_WITH_IE, target_x=tx_throw),
                    Step(State.READY_THROW, duration=16),
                    Step(State.THROW_IE,    duration=20),
                    Step(State.STAND,       duration=25),
                ]))

        # Special après marche — "sortir les épées" (Skadi), etc.
        if self._cfg('enable_special') and self._has(State.BUSY):
            tx_sp = float(L + 100 + random.random() * max(0, (R - L) - 200))
            st_sp = State.WALK_RIGHT if tx_sp > (L + R) / 2 else State.WALK_LEFT
            busy_dur = int(600 + random.random() * 800)
            opts.append((80, [
                Step(st_sp,        target_x=tx_sp),
                Step(State.STAND,  duration=10),
                Step(State.BUSY,   duration=busy_dur),
                Step(State.STAND,  duration=20),
            ]))

        self._start(self._pick(opts))

    # ── IE TOP ────────────────────────────────────────────────────────

    def _new_ie_top_sequence(self) -> None:
        """
        Behaviors quand le perso est sur le DESSUS d'une fenêtre IE.
        Basé sur le bloc 'On Top of IE' du behaviors.xml Shimeji.
        """
        L, _, R, _ = self._L, self._T, self._R, self._B
        opts = []

        # WalkAlongIECeiling / RunAlongIECeiling (Frequency=100)
        # Marche sur la fenêtre (limites IE → on utilise workArea comme fallback)
        tx_walk = float(L + 64 + random.random() * max(0, (R - L) - 128))
        st_walk = State.WALK_RIGHT if tx_walk > self._feet_x_hint else State.WALK_LEFT
        opts.append((100, [Step(st_walk, target_x=tx_walk)]))

        tx_run = float(L + 64 + random.random() * max(0, (R - L) - 128))
        st_run = State.RUN_RIGHT if tx_run > self._feet_x_hint else State.RUN_LEFT
        opts.append((100, [Step(st_run, target_x=tx_run)]))

        # WalkAndSit (Frequency=100)
        if self._has(State.SIT):
            tx_sit = float(L + 100 + random.random() * max(0, (R - L) - 200))
            st_sit = State.WALK_RIGHT if tx_sit > self._feet_x_hint else State.WALK_LEFT
            opts.append((100, [
                Step(st_sit, target_x=tx_sit),
                Step(State.STAND, duration=int(30 + random.random() * 30)),
                Step(State.SIT,   duration=int(300 + random.random() * 300)),
            ]))

        # StandUp / Rest
        opts.append((100, [Step(State.STAND, duration=int(200 + random.random() * 400))]))
        if self._has(State.SLEEP):
            opts.append((50, [Step(State.SLEEP, duration=int(300 + random.random() * 400))]))

        # JumpFromEdgeOfIE (Frequency=100) — sauter du bord avec impulsion
        # Shimeji: Walk→edge, Stand, Falling(InitialVX=±15-20, InitialVY=-20-25)
        # offset_x = fall_vx, offset_y = fall_vy initial (négatif = vers le haut)
        opts.append((100, [
            Step(State.WALK_LEFT,  target_x=float(L + 20)),
            Step(State.STAND,      duration=int(20 + random.random() * 20)),
            Step(State.FALL,       offset_x=-float(15 + random.random() * 5),
                                   offset_y=-float(20 + random.random() * 5)),
        ]))
        opts.append((100, [
            Step(State.WALK_RIGHT, target_x=float(R - 20)),
            Step(State.STAND,      duration=int(20 + random.random() * 20)),
            Step(State.FALL,       offset_x=float(15 + random.random() * 5),
                                   offset_y=-float(20 + random.random() * 5)),
        ]))

        self._start(self._pick(opts))

    # ── WALL ──────────────────────────────────────────────────────────

    def _new_wall_sequence(self) -> None:
        L, T, R, B = self._L, self._T, self._R, self._B
        H = B - T
        opts = []

        # Plafond effectif : plafond IE si disponible, sinon plafond écran
        effective_ceiling = self._ie_ceiling_y if self._ie_ceiling_y is not None else T
        # target_y pour ClimbAlongWall : ceiling + 64 (convention Shimeji)
        wall_top_target = float(effective_ceiling + 64)
        # ClampSafety
        wall_top_target = max(float(T), min(wall_top_target, float(B - 64)))

        # HoldOntoWall
        if self._has(State.GRAB_WALL):
            opts.append((100, [
                Step(State.GRAB_WALL, duration=int(300+random.random()*300)),
            ]))

        # FallFromWall
        opts.append((70, [Step(State.FALL, duration=1)]))

        # TeleportToBottom (Faust) — disparaît du mur → réapparaît au sol
        if 'TeleportFromWall' in self._available_actions:
            opts.append((90, [
                Step(State.TELEPORT, duration=18),       # anim TeleportFromWall (~9 frames×2ticks)
                Step(State.STAND,    teleport_floor=True),  # téléport instantané au sol
                Step(State.FALL,     duration=1),
            ]))

        # ClimbHalfwayAlongWall
        if self._has(State.CLIMB_WALL):
            mid_y = float(T + 64 + random.random() * max(0, H - 128))
            opts.append((100, [
                Step(State.CLIMB_WALL, target_y=mid_y),
                Step(State.FALL, duration=1),
            ]))

        # ClimbAlongWall : XML exact
        # ClimbWall TargetY=top+64 → Offset Y=-64 → Look → ClimbCeiling TargetX=…
        if self._has(State.CLIMB_WALL, State.CLIMB_CEILING):
            # TargetX : calcul selon look_right AVANT Look
            # look_right=False (mur gauche) → Look → True  → going RIGHT → target=L+rand*100
            # look_right=True  (mur droit)  → Look → False → going LEFT  → target=R-rand*100
            if self._look_right:   # mur droit
                tx_c = float(R - random.random() * 100)
            else:                  # mur gauche
                tx_c = float(L + random.random() * 100)

            # look_right APRÈS Look = inverse du look_right actuel
            lr_after_look = not self._look_right
            opts.append((100, [
                Step(State.CLIMB_WALL,    target_y=wall_top_target),
                Step(State.STAND,         offset_y=-64.0),
                Step(State.STAND,         do_look=True),
                # look_right_val = valeur après Look → overrides heuristique
                Step(State.CLIMB_CEILING, target_x=tx_c, look_right_val=lr_after_look),
            ]))

        if not opts:
            self._state = State.FALL
            return

        self._start(self._pick(opts))

    # ── CEILING ───────────────────────────────────────────────────────

    def _new_ceiling_sequence(self) -> None:
        L, _, R, _ = self._L, self._T, self._R, self._B
        W = R - L
        opts = []

        # HoldOntoCeiling
        if self._has(State.GRAB_CEILING):
            opts.append((200, [
                Step(State.GRAB_CEILING, duration=int(100+random.random()*100)),
            ]))

        # FallFromCeiling : Offset Y=+1 → chute
        opts.append((60, [
            Step(State.STAND, offset_y=1.0),
            Step(State.FALL,  duration=1),
        ]))

        # TeleportToBottom (Faust depuis plafond) — disparaît → réapparaît au sol
        if 'TeleportFromWall' in self._available_actions:
            opts.append((90, [
                Step(State.TELEPORT, duration=18),
                Step(State.STAND,    teleport_floor=True),
                Step(State.FALL,     duration=1),
            ]))

        # ClimbAlongCeiling : XML → TargetX=left+64+random*(width-128)
        if self._has(State.CLIMB_CEILING):
            tx = float(L + 64 + random.random() * max(0, W - 128))
            opts.append((100, [
                Step(State.CLIMB_CEILING, target_x=tx),
            ]))

        if not opts:
            self._state = State.FALL
            return

        self._start(self._pick(opts))