"""core/window_detector.py – Détection complète des surfaces de fenêtres Win32."""
from __future__ import annotations
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class WindowRect:
    left:   int
    top:    int
    right:  int
    bottom: int
    title:  str = ""

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x <= self.right and self.top <= y <= self.bottom


@dataclass
class WindowSurfaces:
    """Toutes les surfaces d'une fenêtre ouverte."""
    win:        WindowRect
    # Bords accessibles
    top:        bool = True   # sol (marcher dessus)
    bottom:     bool = True   # plafond (s'accrocher dessous)
    left_wall:  bool = True   # mur gauche
    right_wall: bool = True   # mur droit


if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    user32   = ctypes.windll.user32
    SW_SHOWMINIMIZED = 2
    DWMWA_EXTENDED_FRAME_BOUNDS = 9

    class WINDOWPLACEMENT(ctypes.Structure):
        _fields_ = [
            ("length",           ctypes.c_uint),
            ("flags",            ctypes.c_uint),
            ("showCmd",          ctypes.c_uint),
            ("ptMinPosition",    ctypes.wintypes.POINT),
            ("ptMaxPosition",    ctypes.wintypes.POINT),
            ("rcNormalPosition", ctypes.wintypes.RECT),
        ]

    class WindowDetector:
        IGNORED_TITLES  = {"shimeji", "tray", "program manager"}
        IGNORED_CLASSES = {"Shell_TrayWnd", "DV2ControlHost", "MsgrIMEWindowClass",
                           "WorkerW", "Progman"}
        MIN_WIDTH       = 150
        MIN_HEIGHT      = 60

        def __init__(self):
            self._surfaces: list[WindowSurfaces] = []
            self._rect_cache: list[tuple] = []
            self._rect_cache_time: float = 0.0
            self._dwm = self._check_dwm()

        def _check_dwm(self) -> bool:
            try:
                ctypes.windll.dwmapi.DwmGetWindowAttribute
                return True
            except Exception:
                return False

        def _get_rect(self, hwnd) -> Optional[ctypes.wintypes.RECT]:
            if self._dwm:
                r = ctypes.wintypes.RECT()
                hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
                    hwnd, DWMWA_EXTENDED_FRAME_BOUNDS,
                    ctypes.byref(r), ctypes.sizeof(r))
                if hr == 0:
                    return r
            r = ctypes.wintypes.RECT()
            return r if user32.GetWindowRect(hwnd, ctypes.byref(r)) else None

        def refresh(self) -> None:
            results: list[WindowSurfaces] = []
            # Facteur DPI : convertir pixels physiques Win32 → pixels logiques Qt
            try:
                from PyQt6.QtWidgets import QApplication
                dpr = QApplication.primaryScreen().devicePixelRatio() if QApplication.instance() else 1.0
            except Exception:
                dpr = 1.0

            def enum_cb(hwnd, _):
                try:
                    if not user32.IsWindowVisible(hwnd):
                        return True
                    # Minimisée ?
                    pl = WINDOWPLACEMENT()
                    pl.length = ctypes.sizeof(WINDOWPLACEMENT)
                    user32.GetWindowPlacement(hwnd, ctypes.byref(pl))
                    if pl.showCmd == SW_SHOWMINIMIZED:
                        return True
                    # Classe
                    cb = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, cb, 256)
                    if cb.value in self.IGNORED_CLASSES:
                        return True
                    # Titre
                    tl = user32.GetWindowTextLengthW(hwnd)
                    if tl == 0:
                        return True
                    tb = ctypes.create_unicode_buffer(tl + 1)
                    user32.GetWindowTextW(hwnd, tb, tl + 1)
                    if any(ig in tb.value.lower() for ig in self.IGNORED_TITLES):
                        return True
                    # Rect (coordonnées physiques Win32)
                    r = self._get_rect(hwnd)
                    if r is None:
                        return True
                    w, h = r.right - r.left, r.bottom - r.top
                    if w < self.MIN_WIDTH or h < self.MIN_HEIGHT:
                        return True
                    # Convertir en pixels logiques Qt (÷ devicePixelRatio)
                    def to_logical(v):
                        return int(round(v / dpr))
                    win = WindowRect(
                        to_logical(r.left), to_logical(r.top),
                        to_logical(r.right), to_logical(r.bottom),
                        tb.value)
                    # Vérifier que le bord supérieur est réellement visible
                    if self._is_top_border_visible(hwnd, r):
                        ws = WindowSurfaces(win=win)
                        ws._hwnd = hwnd  # type: ignore[attr-defined]
                        results.append(ws)
                except Exception:
                    pass
                return True

            PROC = ctypes.WINFUNCTYPE(
                ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            user32.EnumWindows(PROC(enum_cb), 0)
            self._surfaces = results

        def _is_top_border_visible(self, hwnd, rect) -> bool:
            """
            Vérifie que le bord supérieur de la fenêtre est visible à l'écran
            en testant plusieurs points sur la ligne du haut.
            Utilise WindowFromPoint pour voir quelle fenêtre est au premier plan.
            """
            try:
                top_y = rect.top + 2  # 2px en dessous du bord
                mid_x = (rect.left + rect.right) // 2
                # Tester le centre et les quarts gauche/droit
                test_points = [
                    (mid_x, top_y),
                    (rect.left + (rect.right - rect.left) // 4, top_y),
                    (rect.left + 3 * (rect.right - rect.left) // 4, top_y),
                ]
                for px, py in test_points:
                    pt = ctypes.wintypes.POINT(px, py)
                    found = user32.WindowFromPoint(pt)
                    if found == hwnd:
                        return True
                    # Aussi accepter si c'est un enfant de la fenêtre
                    parent = found
                    for _ in range(5):
                        parent = user32.GetParent(parent)
                        if parent == hwnd:
                            return True
                        if parent == 0:
                            break
                return False
            except Exception:
                return True  # En cas d'erreur, accepter la fenêtre

        # ── Surfaces accessibles ─────────────────────────────────────

        def get_windows(self) -> list[WindowRect]:
            return [s.win for s in self._surfaces]

        def get_surfaces(self) -> list[WindowSurfaces]:
            return list(self._surfaces)

        # ── Détection de contact ─────────────────────────────────────

        def _get_cached_rects(self) -> list:
            """
            Cache des rects Win32 — rafraîchi max 1x toutes les 33ms (~1 tick).
            Réduit les appels GetWindowRect de N_mascots×N_windows à N_windows/tick.
            """
            import time as _time
            now = _time.monotonic()
            if (now - self._rect_cache_time) < 0.033:
                return self._rect_cache
            try:
                from PyQt6.QtWidgets import QApplication as _QApp
                _dpr = _QApp.primaryScreen().devicePixelRatio() \
                       if _QApp.instance() else 1.0
            except Exception:
                _dpr = 1.0
            _r = ctypes.wintypes.RECT()
            cache = []
            for s in self._surfaces:
                hwnd = getattr(s, '_hwnd', 0)
                if not hwnd:
                    continue
                try:
                    if user32.GetWindowRect(hwnd, ctypes.byref(_r)):
                        left   = int(round(_r.left   / _dpr))
                        top    = int(round(_r.top    / _dpr))
                        right  = int(round(_r.right  / _dpr))
                        bottom = int(round(_r.bottom / _dpr))
                        cache.append((hwnd, left, top, right, bottom,
                                      right - left, bottom - top))
                        continue
                except Exception:
                    pass
                cache.append((hwnd, s.win.left, s.win.top, s.win.right, s.win.bottom,
                              s.win.width, s.win.height))
            self._rect_cache      = cache
            self._rect_cache_time = now
            return cache

        def get_floor_at(self, x: int, y: int, screen_top: int,
                         screen_bottom: int) -> Optional[int]:
            """Retourne le Y du sol IE sous (x, y). Utilise le cache rect.
            Exclut les fenêtres plein-écran et les très grandes fenêtres."""
            TOL = 5  # tolérance stricte comme Shimeji isOn()
            screen_h = screen_bottom - screen_top

            best: Optional[int] = None
            for _, left, top, right, bottom, w, h in self._get_cached_rects():
                if w < 200 or h < 80:
                    continue
                # Exclure les fenêtres trop hautes (quasi-plein-écran = app principale)
                # Elles ne doivent pas servir de sol
                if h > screen_h * 0.7:
                    continue
                if not (left <= x <= right):
                    continue
                if not (screen_top <= top <= screen_bottom):
                    continue
                if abs(y - top) > TOL:
                    continue
                if best is None or top < best:
                    best = top
            return best

        def get_window_current_pos(self, hwnd: int) -> Optional[tuple[int, int]]:
            """Retourne (left, top) actuel de la fenêtre via GetWindowRect direct (temps réel).
            Bypasse le cache _surfaces pour un suivi frame-perfect à 30fps."""
            if not hwnd:
                return None
            try:
                # Appel Win32 direct — pas de cache, résultat instantané
                r = ctypes.wintypes.RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(r)):
                    # Convertir en pixels logiques Qt (÷ devicePixelRatio)
                    try:
                        from PyQt6.QtWidgets import QApplication
                        dpr = QApplication.primaryScreen().devicePixelRatio() \
                              if QApplication.instance() else 1.0
                    except Exception:
                        dpr = 1.0
                    left = int(round(r.left  / dpr))
                    top  = int(round(r.top   / dpr))
                    return (left, top)
            except Exception:
                pass
            return None

        def get_ie_floor_above(self, x: int, y: int,
                               screen_top: int, screen_bottom: int) -> Optional[int]:
            """Y du dessus d'une fenêtre AU-DESSUS de (x, y). Cache rect."""
            screen_h = screen_bottom - screen_top
            best: Optional[int] = None
            for _, left, top, right, bottom, w, h in self._get_cached_rects():
                if w < 200 or h < 80:
                    continue
                if h > screen_h * 0.7:   # exclure plein-écran
                    continue
                if not (left <= x <= right):
                    continue
                if not (screen_top <= top < y - 20):
                    continue
                if best is None or top > best:
                    best = top
            return best

        def get_ceiling_at(self, x: int, y: int,
                           screen_top: int, screen_bottom: int) -> Optional[int]:
            """Y du plafond de fenêtre (bottom d'une fenêtre au-dessus). Cache rect."""
            screen_h = screen_bottom - screen_top
            best: Optional[int] = None
            for _, left, top, right, bottom, w, h in self._get_cached_rects():
                if w < 200 or h < 80:
                    continue
                if h > screen_h * 0.7:   # exclure plein-écran
                    continue
                if not (left <= x <= right):
                    continue
                if bottom > y:
                    continue
                if best is None or bottom > best:
                    best = bottom
            return best

        def get_wall_at(self, x: int, y: int, tolerance: int = 6
                        ) -> tuple[Optional[int], Optional[int]]:
            """Retourne (left_wall_x, right_wall_x) des bords de fenêtres. Cache rect.
            N'active PAS les bords si y == window.top (perso debout dessus, pas dessous)."""
            lwall: Optional[int] = None
            rwall: Optional[int] = None
            for _, left, top, right, bottom, w, h in self._get_cached_rects():
                if h < 80:
                    continue
                # Le perso doit être DANS la hauteur de la fenêtre,
                # pas simplement sur son dessus (y == top serait on_ie_floor)
                if not (top + 5 < y <= bottom):
                    continue
                if abs(x - left) <= tolerance:
                    lwall = left
                if abs(x - right) <= tolerance:
                    rwall = right
            return lwall, rwall

        def is_on_ie_top(self, x: int, y: int, tol: int = 6) -> bool:
            for s in self._surfaces:
                w = s.win
                if w.left <= x <= w.right and abs(y - w.top) <= tol:
                    return True
            return False

        def is_on_ie_bottom(self, x: int, y: int, tol: int = 6) -> bool:
            for s in self._surfaces:
                w = s.win
                if w.left <= x <= w.right and abs(y - w.bottom) <= tol:
                    return True
            return False

        def is_on_ie_left(self, x: int, y: int, tol: int = 6) -> bool:
            for s in self._surfaces:
                w = s.win
                if w.top <= y <= w.bottom and abs(x - w.left) <= tol:
                    return True
            return False

        def is_on_ie_right(self, x: int, y: int, tol: int = 6) -> bool:
            for s in self._surfaces:
                w = s.win
                if w.top <= y <= w.bottom and abs(x - w.right) <= tol:
                    return True
            return False

        def set_window_pos(self, hwnd: int, x: int, y: int) -> None:
            """Déplace une fenêtre Win32 à (x, y) sans la redimensionner ni changer le focus."""
            SWP_NOSIZE       = 0x0001
            SWP_NOZORDER     = 0x0004
            SWP_NOACTIVATE   = 0x0010
            user32.SetWindowPos(hwnd, None, x, y, 0, 0,
                                SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)

        def get_nearest_ie_for_carry(self, mascot_x: int, mascot_y: int,
                                     screen_bottom: int) -> Optional[tuple[int, "WindowRect"]]:
            """
            Retourne (hwnd, WindowRect) de la fenêtre la plus proche du mascot
            candidate pour WalkWithIE.
            N'utilise PAS GetForegroundWindow — on ne veut pas attraper la fenêtre
            que l'utilisateur est en train d'utiliser.
            Critères : taille raisonnable, proche du sol, pas plein écran.
            """
            try:
                from PyQt6.QtWidgets import QApplication as _QApp
                screen_w = int(_QApp.primaryScreen().geometry().width())
                screen_h = int(_QApp.primaryScreen().geometry().height())
            except Exception:
                screen_w, screen_h = 1920, 1080

            # Ne pas utiliser la fenêtre foreground (l'utilisateur l'utilise)
            try:
                fg_hwnd = user32.GetForegroundWindow()
            except Exception:
                fg_hwnd = 0

            best_hwnd: int = 0
            best_win  = None
            best_dist = 9999

            for hwnd, left, top, right, bottom, w, h in self._get_cached_rects():
                if hwnd == fg_hwnd:
                    continue   # skip la fenêtre active
                if w < 200 or h < 80:
                    continue
                # Exclure les fenêtres quasi-plein-écran (taskbar, app maximisées)
                if w > screen_w * 0.9 or h > screen_h * 0.85:
                    continue
                dist_y = abs(bottom - mascot_y)
                if dist_y > 300:
                    continue
                dist_x = abs((left + right) // 2 - mascot_x)
                if dist_x > 800:
                    continue
                score = dist_x + dist_y * 3
                if score < best_dist:
                    best_dist = score
                    from types import SimpleNamespace
                    best_win  = SimpleNamespace(left=left, top=top, right=right,
                                               bottom=bottom, width=w, height=h)
                    best_hwnd = hwnd

            if best_win and best_hwnd:
                return best_hwnd, best_win
            return None

else:
    # Stubs non-Windows — redéfinitions intentionnelles pour compatibilité cross-platform
    class WindowRect:  # type: ignore  # noqa: F811
        def __init__(self):
            self.left = self.top = self.right = self.bottom = 0
            self.title = ""

    class WindowSurfaces:  # type: ignore  # noqa: F811
        def __init__(self):
            self.win = WindowRect()

    class WindowDetector:  # type: ignore
        def refresh(self): pass
        def get_windows(self): return []
        def get_surfaces(self): return []
        def get_floor_at(self, *a): return None
        def get_ie_floor_above(self, *a): return None
        def get_ceiling_at(self, *a): return None
        def get_wall_at(self, *a): return None, None
        def set_window_pos(self, *a): pass
        def get_nearest_ie_for_carry(self, *a): return None
        def get_floor_info_at(self, *a): return None
        def get_window_current_pos(self, *a): return None
        def is_on_ie_top(self, *a): return False
        def is_on_ie_bottom(self, *a): return False
        def is_on_ie_left(self, *a): return False
        def is_on_ie_right(self, *a): return False