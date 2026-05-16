"""ui/mascot_window.py
Fenêtre du personnage — compatible avec le behavior séquentiel TargetX/TargetY.
"""
from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QCursor, QRegion, QBitmap
from PyQt6.QtWidgets import QWidget, QMenu, QApplication

from core.behavior import State, STATE_ACTION_MAP
from core.sprite_engine import AnimationPlayer


class MascotWindow(QWidget):
    chat_requested    = pyqtSignal(object)
    clone_requested   = pyqtSignal(object)
    dismiss_requested = pyqtSignal(object)

    def __init__(self, sprite_engine, behavior_engine, physics_engine,
                 config, mascot_id=0, character_name=""):
        super().__init__()
        self.sprite         = sprite_engine
        self.behavior       = behavior_engine
        self.physics        = physics_engine
        self.config         = config
        self.mascot_id      = mascot_id
        self.character_name = character_name or config.character_name

        self._drag_offset: Optional[QPoint] = None
        self._current_pixmap  = None
        self._anim_player: Optional[AnimationPlayer] = None
        self._prev_state: Optional[State] = None
        self._mask_cache_key: int = -1
        self._tick_count = 0

        # Throw physics — tracking vitesse curseur
        self._last_drag_pos: Optional[QPoint]  = None
        self._throw_vx: float     = 0.0   # cursor.dx mesuré par tick (Shimeji exact)
        self._throw_vy: float     = 0.0   # cursor.dy mesuré par tick
        self._throw_immunity: int = 0
        self._deploying:    bool  = False   # Deploy1/Bouncing one-shot en cours
        self._drag_cursor_x: float  = 0.0
        self._drag_cursor_y: float  = 0.0
        self._prev_cursor_x: float  = 0.0
        self._prev_cursor_y: float  = 0.0
        self._drag_vx:       float  = 0.0
        self._drag_vy:       float  = 0.0

        # Cache écran : évite de scanner QApplication.screens() chaque tick
        self._cached_screen_geom = QApplication.primaryScreen().geometry()
        self._screen_cache_ticks: int = 0   # remettre à 0 → rafraîchi au prochain tick

        # Animation de transition one-shot (StartJumping, StartGrabWall, StartGrabCeiling)
        # Jouée AVANT l'animation principale, physique continue normalement
        self._pre_action_player: Optional[AnimationPlayer] = None

        self._setup_window()
        self._select_action(State.STAND)
        self._initial_show()

        # NB: pas de QTimer ici — le MascotController possède un timer mutualisé
        # qui appelle tick() sur tous les persos en même temps.

        self._topmost_timer = QTimer(self)
        self._topmost_timer.timeout.connect(self._force_topmost)
        self._topmost_timer.start(2000)

    # ── Setup ─────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.resize(128, 160)

    def _initial_show(self):
        screen = QApplication.primaryScreen()
        if screen:
            g = screen.geometry()
            self.move(g.left() + g.width() // 2, g.top() + g.height() // 2)
        self.show()
        self.raise_()
        self._remove_dwm_shadow()

    def _remove_dwm_shadow(self):
        import sys
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 2,  ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
            self._set_topmost(hwnd)
        except Exception:
            pass

    def _force_topmost(self):
        import sys
        if sys.platform != "win32":
            return
        try:
            self._set_topmost(int(self.winId()))
        except Exception:
            pass

    @staticmethod
    def _set_topmost(hwnd):
        import ctypes
        HWND_TOPMOST   = -1
        SWP_NOMOVE     = 0x0002
        SWP_NOSIZE     = 0x0001
        SWP_NOACTIVATE = 0x0010
        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    # ── Sélection d'action ────────────────────────────────────────────

    def _select_pinched_sprite(self) -> None:
        """Sprite Pinched selon la vélocité du curseur (throw_vx = cursor.dx/tick)."""
        # Lisser la vélocité curseur
        self._drag_vx = self._drag_vx * 0.7 + self._throw_vx * 0.3
        dx = self._drag_vx  # positif = curseur va à droite = perso traîne à gauche

        if   dx >  12: name = 'pinch_l3'
        elif dx >   6: name = 'pinch_l2'
        elif dx >   1: name = 'pinch_l1'
        elif dx >  -1: name = 'pinch_default'
        elif dx >  -6: name = 'pinch_r1'
        elif dx > -12: name = 'pinch_r2'
        else:          name = 'pinch_r3'

        action = (self.sprite.get_action(name) or
                  self.sprite.get_action('Pinched') or
                  self.sprite.get_action('Dragged'))
        if action and self._anim_player:
            if self._anim_player.action.name != action.name:
                self._anim_player.reset(action)
        elif action:
            self._anim_player = AnimationPlayer(action)


    def _select_action(self, state: State):
        import random as _r
        # FALLING / THROW → pré-action StartFall (Faust) ou Throwed (Magallan)
        if state == State.FALL:
            fall_a = self.sprite.get_action('Falling')
            if fall_a:
                self.physics.state.gravity      = fall_a.gravity
                self.physics.state.resistance_x = fall_a.resistance_x
                self.physics.state.resistance_y = fall_a.resistance_y
            # Magallan : si lancée (fall_vx != 0), utiliser Throwed (gravity=1 = lent)
            if abs(self.physics.state.fall_vx) > 2.0:
                throwed = (self.sprite.get_action('ThrowedCalm') or
                           self.sprite.get_action('Throwed'))
                if throwed:
                    self.physics.state.gravity      = throwed.gravity
                    self.physics.state.resistance_x = throwed.resistance_x
                    self.physics.state.resistance_y = throwed.resistance_y
                    if self._pre_action_player is None:
                        from core.sprite_engine import ActionDef as _AD
                        p = _AD(throwed.name, throwed.action_type, throwed.border_type,
                                throwed.poses, loop=False)
                        self._pre_action_player = AnimationPlayer(p)
                else:
                    # FallingLight : chute légère avec fall_vx mais sans Throwed
                    # (FrostNova JumpFromEdge, gravity=3 au lieu de 7)
                    light = self.sprite.get_action('FallingLight')
                    if light:
                        self.physics.state.gravity      = light.gravity
                        self.physics.state.resistance_x = light.resistance_x
                        self.physics.state.resistance_y = light.resistance_y
            else:
                # Faust : StartFall (gravity=1.5) ou StartFall2 (gravity=2) — alternance
                sf2 = self.sprite.get_action('StartFall2')
                sf1 = self.sprite.get_action('StartFall')
                startfall = (sf2 if (sf2 and _r.random() < 0.4) else sf1) or sf2
                if startfall and self._pre_action_player is None:
                    from core.sprite_engine import ActionDef as _AD
                    p = _AD(startfall.name, startfall.action_type, startfall.border_type,
                            startfall.poses, loop=False)
                    self._pre_action_player = AnimationPlayer(p)
                    # Gravité douce pendant la pre-action
                    self.physics.state.gravity      = startfall.gravity
                    self.physics.state.resistance_x = startfall.resistance_x
                    self.physics.state.resistance_y = startfall.resistance_y

        # JUMPING : saut linéaire Shimeji (vitesse constante vers la cible, sans gravité)
        if state == State.JUMPING:
            tx, ty = self.behavior.current_jump_target()
            if tx is not None and ty is not None:
                # Lire le bon VelocityParam selon l'action (Jumping/Jumping2/Jumping3)
                jump_act_name = self.behavior.current_jump_action() or 'Jumping'
                jump_action = (self.sprite.get_action(jump_act_name)
                               or self.sprite.get_action('Jumping'))
                vel = jump_action.velocity_param if jump_action else 35.0
                dx = tx - self.physics.state.feet_x
                self.physics.state.jump_target_x = float(tx)
                self.physics.state.jump_target_y = float(ty)
                self.physics.state.jump_velocity = vel
                self.physics.state.jump_active   = True
                # look_right selon la direction horizontale du saut
                self.behavior.look_right = dx > 0
            else:
                self.physics.state.jump_active = False
            # Anim de transition : StartJumping (start_jump1-3) si disponible
            pre = self.sprite.get_action('StartJumping')
            if pre:
                from core.sprite_engine import ActionDef as _AD
                p = _AD(pre.name, pre.action_type, pre.border_type, pre.poses, loop=False)
                self._pre_action_player = AnimationPlayer(p)

        # Transition vers mur : StartGrabWall si disponible
        if state == State.GRAB_WALL:
            pre = self.sprite.get_action('StartGrabWall')
            if pre:
                from core.sprite_engine import ActionDef as _AD
                p = _AD(pre.name, pre.action_type, pre.border_type, pre.poses, loop=False)
                self._pre_action_player = AnimationPlayer(p)

        # Transition vers plafond : StartGrabCeiling si disponible
        if state == State.GRAB_CEILING:
            pre = self.sprite.get_action('StartGrabCeiling')
            if pre:
                from core.sprite_engine import ActionDef as _AD
                p = _AD(pre.name, pre.action_type, pre.border_type, pre.poses, loop=False)
                self._pre_action_player = AnimationPlayer(p)
        # RESISTING → utiliser l'action Resisting (se débat)
        if state == State.RESISTING:
            action = self.sprite.get_action('Resisting')
            if action and self._anim_player:
                if self._anim_player.action.name != 'Resisting':
                    self._anim_player.reset(action)
            elif action:
                self._anim_player = AnimationPlayer(action)
            return

        # WALK_WITH_IE → saisir la fenêtre la plus proche
        if state == State.WALK_WITH_IE:
            if self.physics.state.held_hwnd == 0:
                try:
                    g = self._cached_screen_geom
                    fx, fy = int(self.physics.state.feet_x), int(self.physics.state.feet_y)
                    result = self.physics.wd.get_nearest_ie_for_carry(fx, fy, g.bottom())
                    if result:
                        hwnd, win = result
                        wieact = self.sprite.get_action('WalkWithIe') or self.sprite.get_action('RunWithIe')
                        self.physics.state.held_hwnd       = hwnd
                        self.physics.state.held_win_x      = win.left
                        self.physics.state.held_win_y      = win.top
                        self.physics.state.held_win_w      = win.width
                        self.physics.state.held_win_h      = win.height
                        self.physics.state.held_prev_feet_x = self.physics.state.feet_x
                        self.physics.state.ie_offset_x     = wieact.ie_offset_x if wieact else 0
                        self.physics.state.ie_offset_y     = wieact.ie_offset_y if wieact else -36
                except Exception:
                    pass

        # THROW_IE → lancer la fenêtre tenue
        if state == State.THROW_IE and self.physics.state.held_hwnd != 0:
            try:
                throw_act = self.sprite.get_action('ThrowIe')
                ivx = throw_act.throw_initial_vx if throw_act else 45.0
                igrav = throw_act.throw_gravity   if throw_act else 0.1
                direction = 1.0 if self.behavior.look_right else -1.0
                self.physics.state.throw_hwnd    = self.physics.state.held_hwnd
                self.physics.state.throw_win_x   = float(self.physics.state.held_win_x)
                self.physics.state.throw_win_y   = float(self.physics.state.held_win_y)
                self.physics.state.throw_vx      = ivx * direction
                self.physics.state.throw_vy      = -10.0   # légère impulsion vers le haut
                self.physics.state.throw_gravity  = igrav
                self.physics.state.throw_active   = True
                # Lâcher la fenêtre tenue
                self.physics.state.held_hwnd = 0
            except Exception:
                pass
        candidates = list(STATE_ACTION_MAP.get(state, ["Stand"]))        # Rest (cozy.png) : alterner avec Snooze
        if state == State.SLEEP and 'Rest' in candidates:
            if _r.random() < 0.3:
                candidates = ['Rest']
            else:
                candidates = [c for c in candidates if c != 'Rest']
        action = None
        for name in candidates:
            action = self.sprite.get_action(name)
            if action:
                break
        if action is None:
            for name in self.sprite.action_names():
                action = self.sprite.get_action(name)
                if action:
                    break
        if action:
            if self._anim_player is None:
                self._anim_player = AnimationPlayer(action)
            else:
                self._anim_player.reset(action)

    # ── Boucle principale ─────────────────────────────────────────────

    def tick(self):
        """Appelé par le timer mutualisé du MascotController."""
        if self._anim_player is None:
            return
        self._tick_count += 1

        state = self.behavior.state

        # Animation de transition one-shot (StartJumping, StartGrabWall…)
        # La physique tourne normalement ; seule la pose visuelle est remplacée
        if self._pre_action_player is not None:
            pose_pre = self._pre_action_player.tick()
            if self._pre_action_player.finished:
                self._pre_action_player = None
            else:
                # Rendu avec la pose de transition, physique normale en fond
                _, _, flipped = self._compute_velocity_and_flip(state, pose_pre)
                pixmap = self.sprite.flip_pixmap(pose_pre.pixmap) if flipped else pose_pre.pixmap
                eff_ax = (pixmap.width() - pose_pre.anchor_x) if flipped else pose_pre.anchor_x
                screen_x = int(self.physics.state.feet_x) - eff_ax
                screen_y = int(self.physics.state.feet_y) - pose_pre.anchor_y
                self._current_pixmap = pixmap
                self._render(pixmap, screen_x, screen_y)
                return

        # 1. Mettre à jour les limites WorkArea — cache écran rafraîchi toutes les 30 ticks
        self._screen_cache_ticks += 1
        if self._screen_cache_ticks >= 30:
            self._screen_cache_ticks = 0
            fx, fy = int(self.physics.state.feet_x), int(self.physics.state.feet_y)
            g = QApplication.primaryScreen().geometry()
            for s in QApplication.screens():
                sg = s.geometry()
                if sg.contains(fx, fy):
                    g = sg
                    break
            self._cached_screen_geom = g
        g = self._cached_screen_geom
        self.behavior.set_workarea(g.left(), g.top(), g.right(), g.bottom())
        self.behavior.set_feet_hint(self.physics.state.feet_x, self.physics.state.feet_y)
        # Informer le behavior du plafond IE (bas de fenêtre visible au-dessus)
        try:
            fx, fy = int(self.physics.state.feet_x), int(self.physics.state.feet_y)
            ie_ceil = self.physics.wd.get_ceiling_at(fx, fy, g.top(), g.bottom())
            if ie_ceil is not None and ie_ceil > g.top():
                self.behavior.set_ie_ceiling_y(ie_ceil)
            else:
                self.behavior.set_ie_ceiling_y(None)
            ie_above = self.physics.wd.get_ie_floor_above(fx, fy, g.top(), g.bottom())
            self.behavior.set_ie_floor_y(ie_above)
            # IE visible pour WalkWithIE
            surfaces = self.physics.wd.get_surfaces()
            self.behavior.set_ie_visible(len(surfaces) > 0)
        except Exception:
            self.behavior.set_ie_ceiling_y(None)
            self.behavior.set_ie_floor_y(None)
            self.behavior.set_ie_visible(False)

        # WalkWithIE : déplacer la fenêtre en sync avec le perso
        if state in (State.WALK_WITH_IE, State.FALL_WITH_IE, State.READY_THROW):
            self._tick_walk_with_ie(g.bottom())

        # ThrowIE : animer la fenêtre en vol
        if state == State.THROW_IE or self.physics.state.throw_active:
            self._tick_throw_ie()
        cursor = QCursor.pos()
        cx, cy = float(cursor.x()), float(cursor.y())
        self.behavior.set_cursor(cx, cy)
        # Calculer cursor.dx/dy par tick (comme Shimeji) pendant le drag
        if self._drag_offset is not None:
            self._throw_vx      = cx - self._prev_cursor_x
            self._throw_vy      = cy - self._prev_cursor_y
            self._drag_cursor_x = cx  # curseur courant pour le pendule
        self._prev_cursor_x = cx
        self._prev_cursor_y = cy

        # 2. Appliquer les Offsets en attente
        ox = self.behavior.pop_offset_x()
        if ox is not None:
            if state == State.FALL:
                # offset_x sur FALL = impulsion horizontale (JumpFromEdge)
                self.physics.state.fall_vx = max(-30.0, min(30.0, ox))
            else:
                self.physics.state.feet_x = max(float(g.left()),
                    min(self.physics.state.feet_x + ox, float(g.right())))
        # Offset Y en attente (Shimeji Offset action)
        offset_y = self.behavior.pop_offset_y()
        if offset_y is not None:
            if state == State.FALL:
                # offset_y sur FALL = impulsion verticale initiale (JumpFromEdge InitialVY)
                self.physics.state.fall_vy = max(-60.0, min(0.0, offset_y))
            else:
                self.physics.state.feet_y += offset_y
                self.physics.state.feet_y = max(float(g.top()),
                                                min(self.physics.state.feet_y,
                                                    float(g.bottom())))

        # Téléportation Faust : repositionner instantanément au sol
        if self.behavior.pop_teleport_floor():
            self.physics.state.feet_y = float(g.bottom())
            self.physics.state.fall_vy = 0.0

        # 2b. Pinched sprite AVANT tick() (DRAG seulement, pas RESISTING qui a sa propre anim)
        if state == State.DRAG:
            self._select_pinched_sprite()

        # 3. Avancer l'animation
        pose = self._anim_player.tick()

        # 4. Velocity effective + flip
        eff_vx, eff_vy, flipped = self._compute_velocity_and_flip(state, pose)

        # 5. Pixmap + anchor effectif — flip via cache (évite alloc QPixmap chaque tick)
        pixmap = pose.pixmap
        if flipped:
            pixmap = self.sprite.flip_pixmap(pixmap)
        eff_ax = (pixmap.width() - pose.anchor_x) if flipped else pose.anchor_x
        eff_ay = pose.anchor_y

        # 6. Physique — pour DRAG, on met à jour feet_x/y AVANT le tick physique
        # (garantit que physics reçoit la position courante, pas celle du tick précédent)
        if state in (State.DRAG, State.RESISTING):
            self.physics.state.feet_x = float(self.x() + eff_ax)
            self.physics.state.feet_y = float(self.y() + eff_ay)

        phys = self.physics.tick(
            behavior_state=state,
            pose_vx=eff_vx,
            pose_vy=eff_vy,
            sprite_w=pixmap.width(),
            sprite_h=pixmap.height(),
            anchor_x=eff_ax,
            anchor_y=eff_ay,
        )

        # 7. Behavior tick (avec position réelle pour les targets)
        new_state = self.behavior.tick(
            feet_x        = phys.feet_x,
            feet_y        = phys.feet_y,
            on_floor      = phys.on_any_floor,
            at_left_edge  = phys.at_left_edge,
            at_right_edge = phys.at_right_edge,
            on_wall       = phys.on_any_wall,
            on_ceiling    = phys.on_any_ceiling,
            on_ie_top     = phys.on_ie_floor,
        )

        # 8. Changer d'action si état change
        if new_state != self._prev_state:
            # Lâcher la fenêtre si on quitte WALK_WITH_IE sans ThrowIE
            if self._prev_state in (State.WALK_WITH_IE, State.FALL_WITH_IE, State.READY_THROW) \
               and new_state not in (State.WALK_WITH_IE, State.FALL_WITH_IE,
                                     State.READY_THROW, State.THROW_IE):
                self.physics.state.held_hwnd = 0
            # Wokeup : animation de réveil quand on quitte SLEEP → STAND
            if self._prev_state == State.SLEEP and new_state == State.STAND:
                wokeup = self.sprite.get_action('Wokeup')
                if wokeup and self._pre_action_player is None:
                    from core.sprite_engine import ActionDef as _AD
                    p = _AD(wokeup.name, wokeup.action_type, wokeup.border_type,
                            wokeup.poses, loop=False)
                    self._pre_action_player = AnimationPlayer(p)
            # StartFallFromCeiling : pre-action quand Faust lâche le plafond
            if self._prev_state in (State.GRAB_CEILING, State.CLIMB_CEILING) \
               and new_state == State.FALL:
                sfceil = self.sprite.get_action('StartFallFromCeiling')
                if sfceil and self._pre_action_player is None:
                    from core.sprite_engine import ActionDef as _AD
                    p = _AD(sfceil.name, sfceil.action_type, sfceil.border_type,
                            sfceil.poses, loop=False)
                    self._pre_action_player = AnimationPlayer(p)
                # FallingLight : gravité douce si disponible (FrostNova chute depuis hauteur)
                light = self.sprite.get_action('FallingLight')
                if light:
                    self.physics.state.gravity      = light.gravity
                    self.physics.state.resistance_x = light.resistance_x
                    self.physics.state.resistance_y = light.resistance_y
            # FallingLight aussi depuis un mur
            if self._prev_state in (State.GRAB_WALL, State.CLIMB_WALL) \
               and new_state == State.FALL:
                light = self.sprite.get_action('FallingLight')
                if light:
                    self.physics.state.gravity      = light.gravity
                    self.physics.state.resistance_x = light.resistance_x
                    self.physics.state.resistance_y = light.resistance_y
            self._select_action(new_state)
            self._prev_state = new_state

        # 9. Atterrissage depuis chute
        if self._throw_immunity > 0:
            self._throw_immunity -= 1
        if self._deploying:
            if self._anim_player and self._anim_player.finished:
                self._deploying = False
                self.behavior.land()   # → _new_floor_sequence
                self._select_action(self.behavior.state)
                self._prev_state = self.behavior.state
        # Bouncing state: attendre la fin de l'animation
        elif state == State.BOUNCING and self._anim_player and self._anim_player.finished:
            self.behavior.land()
            self._select_action(self.behavior.state)
        elif state in (State.FALL, State.JUMPING) and phys.on_any_floor \
                and self._throw_immunity == 0 and phys.fall_vy >= 0 \
                and not phys.jump_active:
            # Bouncing (FrostNova) ou Deploy1 (autres) — one-shot
            deploy = (self.sprite.get_action('Bouncing') or
                      self.sprite.get_action('Deploy2') or
                      self.sprite.get_action('Deploy1') or
                      self.sprite.get_action('DeployEnter'))
            if deploy:
                from core.sprite_engine import ActionDef
                d = ActionDef(name=deploy.name, action_type=deploy.action_type,
                              border_type=deploy.border_type, poses=deploy.poses, loop=False)
                self._deploying = True
                self._anim_player.reset(d)
                # Forcer STAND pour éviter que FALL+on_floor se re-déclenche chaque tick
                self.behavior.force_state(State.STAND)
                self._prev_state = State.STAND
            else:
                self.behavior.land()
                self._select_action(self.behavior.state)

        # 10. Position écran
        if state in (State.DRAG, State.RESISTING):
            self._current_pixmap = pixmap
            self._render(pixmap, self.x(), self.y())
            return
        screen_x = int(phys.feet_x) - eff_ax
        screen_y = int(phys.feet_y) - eff_ay

        self._current_pixmap = pixmap
        self._render(pixmap, screen_x, screen_y)

    # ── Velocity et flip ──────────────────────────────────────────────

    def _compute_velocity_and_flip(self, state: State, pose) -> tuple[float, float, bool]:
        vx, vy = pose.velocity_x, pose.velocity_y
        ws = getattr(self.config, 'walk_speed', 1.0)  # multiplicateur de vitesse

        if state in (State.WALK_LEFT, State.RUN_LEFT):
            return vx * ws, vy, False
        if state in (State.WALK_RIGHT, State.RUN_RIGHT):
            return -vx * ws, vy, True
        if state in (State.STAND, State.SIT, State.SLEEP, State.BUSY,
                     State.TALKING):
            return 0.0, 0.0, not self.behavior.look_right
        if state == State.FALL:
            return 0.0, 0.0, not self.behavior.look_right
        if state in (State.GRAB_WALL, State.CLIMB_WALL):
            # Shimeji: look_right=True → sprite flippé (mur droit)
            #          look_right=False → sprite natif (mur gauche)
            return vx, vy, self.behavior.look_right
        if state in (State.GRAB_CEILING, State.CLIMB_CEILING):
            # Shimeji: look_right=True  → sprite flippé, vx négative → va DROITE (+vx)
            #          look_right=False → sprite natif, vx négative → va GAUCHE (-vx)
            # (même convention que Walk)
            if self.behavior.look_right:
                return -vx, vy, True    # droite: negate+flip
            else:
                return vx, vy, False    # gauche: natif
        if state in (State.DRAG, State.RESISTING):
            return 0.0, 0.0, not self.behavior.look_right
        if state == State.JUMPING:
            # Flip selon la direction horizontale du saut
            if self.physics.state.jump_active:
                flipped = self.physics.state.jump_vx > 0
            else:
                flipped = not self.behavior.look_right
            return 0.0, 0.0, flipped
        if state == State.BOUNCING:
            return 0.0, 0.0, not self.behavior.look_right
        if state == State.TELEPORT:
            return 0.0, 0.0, self.behavior.look_right
        if state in (State.WALK_WITH_IE, State.READY_THROW, State.THROW_IE, State.FALL_WITH_IE):
            if self.behavior.look_right:
                return -vx * ws, vy, True
            else:
                return vx * ws, vy, False
        return vx, vy, not self.behavior.look_right

    # ── Rendu ─────────────────────────────────────────────────────────

    def _render(self, pixmap, x: int, y: int):
        w, h = pixmap.width(), pixmap.height()
        if self.width() != w or self.height() != h:
            self.resize(w, h)
        self.move(x, y)
        pkey = pixmap.cacheKey()
        if pkey != self._mask_cache_key:
            self._mask_cache_key = pkey
            try:
                img = pixmap.toImage()
                img = img.convertToFormat(img.Format.Format_ARGB32_Premultiplied)
                bmp = QBitmap.fromImage(img.createAlphaMask())
                if not bmp.isNull():
                    self.setMask(QRegion(bmp))
                else:
                    self.clearMask()
            except Exception:
                self.clearMask()
        self.update()

    def paintEvent(self, event):
        if self._current_pixmap is None:
            return
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(0, 0, self._current_pixmap)
        # Debug overlay
        if getattr(self.config, 'debug_overlay', False):
            from PyQt6.QtGui import QColor, QFont
            phys = self.physics.state
            p.setFont(QFont("Courier", 7))
            p.setPen(QColor(255, 255, 0, 220))
            lines = [
                self.behavior.state.name[:10],
                f"f({phys.feet_x:.0f},{phys.feet_y:.0f})",
                f"v({phys.fall_vx:.1f},{phys.fall_vy:.1f})",
            ]
            for i, line in enumerate(lines):
                p.drawText(2, 10 + i * 10, line)
        p.end()

    # ── Souris ────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Shimeji-ee : le curseur se positionne TOUJOURS sur le haut du sprite Pinched
            # (ImageAnchor.x horizontal, Y=0 vertical = sommet du sprite)
            # Le perso "pend" sous le curseur depuis ce point fixe.
            pinch = self.sprite.get_action('pinch_default') or self.sprite.get_action('Pinched')
            if pinch and pinch.poses:
                grab_x = pinch.poses[0].anchor_x   # centré horizontalement (64)
            else:
                grab_x = self.width() // 2
            # Offset = point dans la fenêtre où le curseur doit rester fixé
            self._drag_offset   = QPoint(grab_x, 0)
            self._last_drag_pos = None
            self._throw_vx      = 0.0
            self._throw_vy      = 0.0
            self._deploying     = False
            self._drag_vx       = 0.0
            self._drag_vy       = 0.0
            self._drag_cursor_x = float(event.globalPosition().x())
            self._drag_cursor_y = float(event.globalPosition().y())
            self.behavior.notify_grabbed()
            self._select_pinched_sprite()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if self._drag_offset and event.buttons() & Qt.MouseButton.LeftButton:
            np = event.globalPosition().toPoint() - self._drag_offset
            self.move(np)
            self._drag_cursor_x = float(event.globalPosition().x())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset   = None
            self._last_drag_pos = None

            # Synchroniser feet_x/y DEPUIS la position actuelle de la fenêtre
            # en utilisant l'anchor de l'animation Falling (pas Pinched).
            # C'est critique : sur le premier tick FALL, screen_x = feet_x - eff_ax_falling
            # Si on utilise l'anchor Pinched ici et que Falling a un anchor différent → saut.
            fall_action = self.sprite.get_action('Falling')
            if fall_action and fall_action.poses:
                ax = fall_action.poses[0].anchor_x
                ay = fall_action.poses[0].anchor_y
            elif self._current_pixmap:
                ax = self._current_pixmap.width() // 2
                ay = self._current_pixmap.height()
            else:
                ax, ay = 64, 128
            self.physics.state.feet_x = float(self.x() + ax)
            self.physics.state.feet_y = float(self.y() + ay)

            # Vitesse de lancer (cursor.dx/dy par tick, comme Shimeji)
            self.physics.state.fall_vx = max(-60.0, min(60.0, self._throw_vx))
            self.physics.state.fall_vy = max(-60.0, min(60.0, self._throw_vy))
            if fall_action:
                self.physics.state.gravity      = fall_action.gravity
                self.physics.state.resistance_x = fall_action.resistance_x
                self.physics.state.resistance_y = fall_action.resistance_y
            self._throw_vx = 0.0
            self._throw_vy = 0.0
            self._deploying = False
            self.behavior.notify_released()
            self._select_action(State.FALL)
            self._throw_immunity = 8

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.chat_requested.emit(self)

    # ── Menu contextuel ───────────────────────────────────────────────

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#1a1a2e; color:#e0e0e0;
                    border:1px solid #4a4a8a; border-radius:6px;
                    padding:4px; font-size:13px; }
            QMenu::item { padding:6px 20px; border-radius:4px; }
            QMenu::item:selected { background:#4a4a8a; }
        """)
        profile_act = menu.addAction(f"◈  {self.character_name}")
        profile_act.setEnabled(False)
        menu.addSeparator()
        chat_act    = menu.addAction("💬 Discuter")
        info_act    = menu.addAction("🪪 Profil & Relations")
        menu.addSeparator()
        clone_act   = menu.addAction("🐑 Dupliquer")
        menu.addSeparator()
        dismiss_act = menu.addAction("✖ Retirer")
        action = menu.exec(pos)
        if action == chat_act:
            self.chat_requested.emit(self)
        elif action == info_act:
            self._show_profile()
        elif action == clone_act:
            self.clone_requested.emit(self)
        elif action == dismiss_act:
            self.dismiss_requested.emit(self)

    def _show_profile(self):
        try:
            from ui.profile_dialog import ProfileDialog
            controller = getattr(self, '_controller', None)
            if controller:
                dlg = ProfileDialog(self, controller)
                dlg.show()
        except Exception as e:
            print(f"[Profile] Erreur : {e}")

    # ── API ───────────────────────────────────────────────────────────

    def mascot_position(self) -> QPoint:
        return self.pos()

    def _tick_walk_with_ie(self, screen_bottom: int) -> None:
        """Déplace la fenêtre tenue en sync avec le mouvement du perso.
        Relâche automatiquement si l'utilisateur déplace la fenêtre manuellement."""
        s = self.physics.state
        if s.held_hwnd == 0:
            return
        try:
            # Vérifier si l'utilisateur a bougé la fenêtre manuellement
            # (position réelle ≠ position attendue → l'utilisateur la tient)
            actual = self.physics.wd.get_window_current_pos(s.held_hwnd)
            if actual is not None:
                actual_x, actual_y = actual
                expected_x, expected_y = s.held_win_x, s.held_win_y
                if abs(actual_x - expected_x) > 15 or abs(actual_y - expected_y) > 15:
                    # L'utilisateur a déplacé la fenêtre → relâcher
                    s.held_hwnd = 0
                    return

            delta_x = s.feet_x - s.held_prev_feet_x
            s.held_prev_feet_x = s.feet_x
            if abs(delta_x) < 0.5:
                new_win_y = int(s.feet_y + s.ie_offset_y - s.held_win_h)
                new_win_y = min(new_win_y, screen_bottom - s.held_win_h)
                self.physics.wd.set_window_pos(s.held_hwnd, s.held_win_x, new_win_y)
                s.held_win_y = new_win_y
                return
            new_win_x = int(s.held_win_x + delta_x)
            new_win_y = int(s.feet_y + s.ie_offset_y - s.held_win_h)
            new_win_y = min(new_win_y, screen_bottom - s.held_win_h)
            self.physics.wd.set_window_pos(s.held_hwnd, new_win_x, new_win_y)
            s.held_win_x = new_win_x
            s.held_win_y = new_win_y
        except Exception:
            s.held_hwnd = 0

    def _tick_throw_ie(self) -> None:
        """Anime la fenêtre lancée. Arrête si l'utilisateur l'attrape en vol."""
        s = self.physics.state
        if not s.throw_active or s.throw_hwnd == 0:
            return
        try:
            # Détecter si l'utilisateur a attrapé la fenêtre
            actual = self.physics.wd.get_window_current_pos(s.throw_hwnd)
            if actual is not None:
                actual_x, actual_y = actual
                if abs(actual_x - s.throw_win_x) > 20 or abs(actual_y - s.throw_win_y) > 20:
                    s.throw_active = False
                    s.throw_hwnd   = 0
                    return

            s.throw_vy    += s.throw_gravity
            s.throw_win_x += s.throw_vx
            s.throw_win_y += s.throw_vy
            g = self._cached_screen_geom
            win_w = s.held_win_w if s.held_win_w > 0 else 400
            win_h = s.held_win_h if s.held_win_h > 0 else 300
            if s.throw_win_x < g.left():
                s.throw_win_x = float(g.left())
                s.throw_vx = abs(s.throw_vx) * 0.5
            elif s.throw_win_x + win_w > g.right():
                s.throw_win_x = float(g.right() - win_w)
                s.throw_vx = -abs(s.throw_vx) * 0.5
            if s.throw_win_y + win_h >= g.bottom():
                s.throw_win_y = float(g.bottom() - win_h)
                s.throw_active = False
            self.physics.wd.set_window_pos(s.throw_hwnd,
                                            int(s.throw_win_x), int(s.throw_win_y))
            if not s.throw_active:
                s.throw_hwnd = 0
        except Exception:
            s.throw_active = False
            s.throw_hwnd   = 0

    def close_mascot(self):
        self._topmost_timer.stop()
        self.close()