"""core/monitor_manager.py – Gestion multi-écran."""
from __future__ import annotations
import sys
from dataclasses import dataclass


@dataclass
class Monitor:
    left: int
    top: int
    right: int
    bottom: int
    is_primary: bool = False

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x <= self.right and self.top <= y <= self.bottom

    def clamp_x(self, x: int, margin: int = 0) -> int:
        return max(self.left + margin, min(x, self.right - margin))

    def clamp_y(self, y: int, margin: int = 0) -> int:
        return max(self.top + margin, min(y, self.bottom - margin))


class MonitorManager:
    def __init__(self):
        self._monitors: list[Monitor] = []
        self.refresh()

    def refresh(self) -> None:
        self._monitors = self._detect_monitors()
        if not self._monitors:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.geometry()
                self._monitors = [Monitor(geo.left(), geo.top(), geo.right(), geo.bottom(), True)]

    def _detect_monitors(self) -> list[Monitor]:
        monitors: list[Monitor] = []

        if sys.platform == "win32":
            import ctypes
            import ctypes.wintypes

            # MONITORINFO n'est pas dans ctypes.wintypes sur Python 3.13 — on le définit
            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize",    ctypes.c_uint),
                    ("rcMonitor", ctypes.wintypes.RECT),
                    ("rcWork",    ctypes.wintypes.RECT),
                    ("dwFlags",   ctypes.c_uint),
                ]

            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.c_bool,
                ctypes.wintypes.HMONITOR,
                ctypes.wintypes.HDC,
                ctypes.POINTER(ctypes.wintypes.RECT),
                ctypes.wintypes.LPARAM,
            )

            def callback(hmon, hdc, rect_ptr, _):
                try:
                    info = MONITORINFO()
                    info.cbSize = ctypes.sizeof(MONITORINFO)
                    ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info))
                    is_primary = bool(info.dwFlags & 1)
                    r = info.rcMonitor
                    monitors.append(Monitor(
                        left=r.left, top=r.top,
                        right=r.right, bottom=r.bottom,
                        is_primary=is_primary,
                    ))
                except Exception as e:
                    print(f"[Monitor] Erreur callback : {e}")
                return True

            ctypes.windll.user32.EnumDisplayMonitors(
                None, None, MONITORENUMPROC(callback), 0
            )
        else:
            from PyQt6.QtWidgets import QApplication
            for screen in QApplication.screens():
                geo = screen.geometry()
                monitors.append(Monitor(
                    geo.left(), geo.top(), geo.right(), geo.bottom(),
                    screen == QApplication.primaryScreen(),
                ))

        return monitors

    def monitors(self) -> list[Monitor]:
        return list(self._monitors)

    def primary(self) -> Monitor:
        for m in self._monitors:
            if m.is_primary:
                return m
        return self._monitors[0] if self._monitors else Monitor(0, 0, 1920, 1080, True)

    def monitor_at(self, x: int, y: int) -> Monitor:
        for m in self._monitors:
            if m.contains(x, y):
                return m
        return self.primary()

    def global_bounds(self) -> tuple[int, int, int, int]:
        left   = min(m.left   for m in self._monitors)
        top    = min(m.top    for m in self._monitors)
        right  = max(m.right  for m in self._monitors)
        bottom = max(m.bottom for m in self._monitors)
        return left, top, right, bottom

    def is_valid_position(self, x: int, y: int) -> bool:
        return any(m.contains(x, y) for m in self._monitors)