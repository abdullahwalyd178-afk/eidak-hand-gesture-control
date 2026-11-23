# -*- coding: utf-8 -*-
"""Camera management and diagnostics for Eidak.

Split out of hand_gesture_control.py (step 0, mechanical - no behavior change).
fix/camera-install adds: startup progress + last-working-camera memory (item 10),
failure classification (item 11), strict selection + IR/virtual camera skip
(item 12), non-blocking reconnect (item 13), freeze detection + MJPG (item 14).
"""

from __future__ import annotations

import platform
import time
from typing import Callable, List, Optional, Tuple

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover - reported nicely at runtime
    cv2 = None

# Failure classes for camera opening (item 11): each gets its own user guidance.
OK = "OK"
NO_DEVICE = "NO_DEVICE"                  # nothing opened at all: absent / busy / driver
OPENED_NO_FRAMES = "OPENED_NO_FRAMES"    # opened but delivered nothing: usually privacy block or a busy app
BLACK_FRAMES = "BLACK_FRAMES"            # frames arrive but are black: covered lens / IR-only camera

PRIVACY_HINT = "Windows Settings > Privacy & security > Camera: allow desktop apps (ms-settings:privacy-webcam)"


def classify_attempt(opened: bool, got_frames: bool, mean_brightness: float,
                     black_threshold: float = 5.0) -> str:
    """Pure classification of one open attempt (item 11)."""
    if not opened:
        return NO_DEVICE
    if not got_frames:
        return OPENED_NO_FRAMES
    if mean_brightness < black_threshold:
        return BLACK_FRAMES
    return OK


def looks_grayscale(frame: np.ndarray, channel_spread: float = 4.0) -> bool:
    """Heuristic [untested on real IR hardware]: IR / Windows Hello cameras deliver
    R~G~B frames. Real color cameras almost never do. (item 12)"""
    if frame is None or frame.size == 0 or frame.ndim < 3 or frame.shape[2] < 3:
        return True
    b = frame[:, :, 0].astype(np.float32)
    g = frame[:, :, 1].astype(np.float32)
    r = frame[:, :, 2].astype(np.float32)
    spread = float(np.mean(np.abs(r - b)) + np.mean(np.abs(g - b)))
    return spread < channel_spread


# --------------------------------------------------------------------------
# Camera manager: the part that treats the camera as unreliable hardware
# --------------------------------------------------------------------------
class CameraManager:
    """Opens the camera defensively and recovers when frames stop flowing.

    - Probes several camera indices and several OS backends.
    - Verifies real, non-black, non-grayscale frames before accepting a camera.
    - Remembers the last working (index, backend) and tries it first (item 10).
    - Detects mid-run freezes/disconnects and reconnects in short, non-blocking
      attempts pinned to the camera the user already chose (items 12, 13, 14).
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.cap = None
        self.active_index: Optional[int] = None
        self.active_backend: Optional[int] = None
        self.backend_name = ""
        self._fail_frames = 0
        self._last_reconnect_attempt = 0.0
        self._reconnect_delay = 1.0
        self.last_error = ""
        self.failure_kind = ""            # one of the classify_attempt codes
        self.low_light = False
        self._last_sig: Optional[np.ndarray] = None
        self._same_since: Optional[float] = None

    # -- probing ------------------------------------------------------------
    def _backends(self) -> List[Tuple[int, str]]:
        system = platform.system()
        if cv2 is None:
            return []
        if system == "Windows":
            # CAP_ANY on Windows just retries DSHOW/MSMF with extra latency (item 10)
            return [(cv2.CAP_DSHOW, "DirectShow"), (cv2.CAP_MSMF, "MediaFoundation")]
        if system == "Darwin":
            return [(cv2.CAP_AVFOUNDATION, "AVFoundation"), (cv2.CAP_ANY, "Auto")]
        return [(cv2.CAP_V4L2, "V4L2"), (cv2.CAP_ANY, "Auto")]

    def _indices(self) -> List[int]:
        preferred = self.cfg.get("camera_index", -1)
        order = list(range(0, 5))
        if isinstance(preferred, int) and preferred >= 0:
            order = [preferred] + [i for i in order if i != preferred]
        return order

    def _probe_plan(self) -> List[Tuple[int, int, str]]:
        """(index, backend, name) attempts, best-known first (item 10)."""
        backends = self._backends()
        plan: List[Tuple[int, int, str]] = []
        last = self.cfg.get("last_camera") or {}
        li, lb = last.get("index"), last.get("backend")
        name_of = {b: n for b, n in backends}
        if isinstance(li, int) and isinstance(lb, int) and lb in name_of:
            plan.append((li, lb, name_of[lb] + " (last working)"))
        strict = bool(self.cfg.get("camera_strict")) and isinstance(self.cfg.get("camera_index"), int) \
            and self.cfg.get("camera_index", -1) >= 0
        indices = [self.cfg["camera_index"]] if strict else self._indices()
        for index in indices:
            for backend, name in backends:
                if plan and index == plan[0][0] and backend == plan[0][1]:
                    continue
                plan.append((index, backend, name))
        return plan

    def _configure(self, cap) -> None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg["frame_width"])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg["frame_height"])
        cap.set(cv2.CAP_PROP_FPS, 30)
        if self.cfg.get("mjpg", True):
            # USB cameras at 720p need MJPG or the link starves (item 14)
            try:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            except Exception:
                pass
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # deliver the freshest frame (item 14)
        except Exception:
            pass

    def _validate(self, cap, budget_sec: float = 2.5, need: int = 3) -> Tuple[str, Optional[np.ndarray]]:
        """Require several real, non-black frames before trusting a camera.
        Returns (classification, last_frame)."""
        deadline = time.time() + budget_sec
        got = 0
        last = None
        while time.time() < deadline and got < need:
            ok, frame = cap.read()
            if ok and frame is not None and frame.size > 0:
                last = frame
                if float(np.mean(frame)) > 5.0:
                    got += 1
            else:
                time.sleep(0.05)
        # OK only when we actually collected `need` good frames: one lucky
        # bright frame is not proof of a healthy stream (advisor review fix).
        if got >= need and last is not None:
            return classify_attempt(True, True, float(np.mean(last))), last
        if last is not None and float(np.mean(last)) <= 5.0:
            return classify_attempt(True, True, float(np.mean(last))), last  # black frames
        return classify_attempt(True, False, 0.0), None

    # -- open / close ---------------------------------------------------------
    def open(self, progress: Optional[Callable[[str], None]] = None) -> bool:
        """Full probe. Prints progress as it goes (item 10)."""
        self.release()
        say = progress or (lambda msg: None)
        attempts = self._probe_plan()
        total = len(attempts)
        saw_opened_no_frames = False
        saw_black = False
        for n, (index, backend, name) in enumerate(attempts, start=1):
            say(f"Trying camera {index} via {name} ({n}/{total})...")
            cap = None
            try:
                cap = cv2.VideoCapture(index, backend)
                if not cap.isOpened():
                    cap.release()
                    continue
                self._configure(cap)
                verdict, frame = self._validate(cap)
                if verdict == OK and frame is not None and self.cfg.get("skip_grayscale_cameras", True) \
                        and looks_grayscale(frame):
                    # IR / virtual cameras open fine but are useless for hand tracking (item 12)
                    say(f"Camera {index} via {name} looks grayscale/IR - skipping")
                    cap.release()
                    saw_black = True
                    continue
                if verdict == OK:
                    self.cap = cap
                    self.active_index = index
                    self.active_backend = backend
                    self.backend_name = name.replace(" (last working)", "")
                    self._fail_frames = 0
                    self._reconnect_delay = 1.0
                    self.last_error = ""
                    self.failure_kind = ""
                    self._last_sig = None
                    self._same_since = None
                    self.cfg["last_camera"] = {"index": index, "backend": backend}
                    return True
                saw_opened_no_frames = saw_opened_no_frames or verdict == OPENED_NO_FRAMES
                saw_black = saw_black or verdict == BLACK_FRAMES
                self.last_error = f"camera {index} via {name}: {verdict}"
                cap.release()
            except Exception as exc:
                self.last_error = str(exc)
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
        # Classify the overall failure so run() can say something useful (item 11)
        self.failure_kind = OPENED_NO_FRAMES if saw_opened_no_frames else (BLACK_FRAMES if saw_black else NO_DEVICE)
        self.last_error = self.last_error or "No working camera found"
        return False

    def _quick_reopen(self) -> bool:
        """One short attempt on the SAME camera (<1s budget), so the UI thread
        never freezes for tens of seconds during reconnect (items 12, 13)."""
        if self.active_index is None or self.active_backend is None:
            return False
        cap = None
        try:
            cap = cv2.VideoCapture(self.active_index, self.active_backend)
            if not cap.isOpened():
                cap.release()
                return False
            self._configure(cap)
            verdict, _ = self._validate(cap, budget_sec=0.8, need=2)
            if verdict == OK:
                old = self.cap
                self.cap = cap
                if old is not None:
                    try:
                        old.release()
                    except Exception:
                        pass
                self._fail_frames = 0
                self._reconnect_delay = 1.0
                self._last_sig = None
                self._same_since = None
                return True
            cap.release()
        except Exception as exc:
            self.last_error = str(exc)
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
        return False

    # -- reading ---------------------------------------------------------------
    @staticmethod
    def _signature(frame: np.ndarray) -> np.ndarray:
        return frame[::16, ::16].astype(np.int16)

    def read(self) -> Tuple[bool, Optional[np.ndarray], str]:
        """Returns (ok, frame, status_message). Reconnects automatically in
        short non-blocking attempts (item 13)."""
        if self.cap is None:
            # The old handle was released after a failure; retry the quick
            # reopen on the same backoff instead of giving up entirely.
            if self.active_index is None or self.active_backend is None:
                return False, None, "Camera is not open"
            now = time.time()
            if now - self._last_reconnect_attempt >= self._reconnect_delay:
                self._last_reconnect_attempt = now
                if self._quick_reopen():
                    return False, None, "Camera reconnected"
                self._reconnect_delay = min(self._reconnect_delay * 2, float(self.cfg["camera_reconnect_max_sec"]))
            return False, None, "Reconnecting camera... check the cable or close other camera apps"
        try:
            ok, frame = self.cap.read()
        except Exception as exc:
            ok, frame = False, None
            self.last_error = str(exc)
        if ok and frame is not None and frame.size > 0:
            self._fail_frames = 0
            brightness = float(np.mean(frame))
            self.low_light = brightness < float(self.cfg.get("low_light_threshold", 35))
            # A frozen driver keeps delivering the SAME frame: detect and recover (item 14)
            sig = self._signature(frame)
            now = time.time()
            if self._last_sig is not None and float(np.mean(np.abs(sig - self._last_sig))) < 0.5:
                if self._same_since is None:
                    self._same_since = now
                elif now - self._same_since > float(self.cfg.get("freeze_reconnect_sec", 4.0)):
                    self._same_since = None
                    self._last_sig = None
                    self._fail_frames = 15  # treat as a freeze: trigger the recovery path
                    return False, None, "Camera picture froze - reconnecting..."
            else:
                self._same_since = None
            self._last_sig = sig
            return True, frame, ""
        self._fail_frames += 1
        if self._fail_frames < 15:
            return False, None, "Camera frame dropped..."
        # The camera froze or was unplugged: try to bring it back, briefly (item 13)
        now = time.time()
        if now - self._last_reconnect_attempt >= self._reconnect_delay:
            self._last_reconnect_attempt = now
            # Release the OLD handle BEFORE retrying: many Windows cameras allow
            # only one connection, so keeping the broken handle open makes every
            # later reopen attempt fail (advisor review fix).
            self._release_handle()
            if self._quick_reopen():
                return False, None, "Camera reconnected"
            self._reconnect_delay = min(self._reconnect_delay * 2, float(self.cfg["camera_reconnect_max_sec"]))
        return False, None, "Reconnecting camera... check the cable or close other camera apps"

    def _release_handle(self) -> None:
        old = self.cap
        self.cap = None
        if old is not None:
            try:
                old.release()
            except Exception:
                pass

    def release(self) -> None:
        self._release_handle()


# --------------------------------------------------------------------------
# Camera listing / diagnostics (for the "the camera does not work" moments)
# --------------------------------------------------------------------------
def list_cameras(cfg: dict) -> int:
    """--list-cameras: show what each index/backend pair gives (item 12)."""
    if cv2 is None:
        print("OpenCV is not installed. Run:  pip install -r requirements.txt")
        return 1
    probe = CameraManager({**cfg, "skip_grayscale_cameras": False})
    for index in probe._indices():
        for backend, name in probe._backends():
            cap = None
            try:
                cap = cv2.VideoCapture(index, backend)
                if not cap.isOpened():
                    continue
                ok, frame = cap.read()
                if ok and frame is not None and frame.size > 0:
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    kind = "grayscale/IR?" if looks_grayscale(frame) else "color"
                    print(f"camera {index} via {name:<16} : {w}x{h} {kind}  ->  --camera {index}")
            except Exception:
                pass
            finally:
                if cap is not None:
                    cap.release()
    return 0


def diagnose_cameras(cfg: dict) -> int:
    lines: List[str] = []

    def out(msg: str) -> None:
        print(msg)
        lines.append(msg)

    out("Eidak camera diagnostics")
    out("=" * 40)
    if cv2 is None:
        out("OpenCV is not installed. Run:  pip install -r requirements.txt")
        _write_report(lines)
        return 1
    manager = CameraManager(cfg)
    found_any = False
    for index in manager._indices():
        for backend, name in manager._backends():
            cap = None
            try:
                cap = cv2.VideoCapture(index, backend)
                if not cap.isOpened():
                    out(f"camera {index} via {name:<16} : not available ({NO_DEVICE})")
                    continue
                verdict, frame = manager._validate(cap)
                if verdict == OK:
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    kind = "grayscale/IR?" if frame is not None and looks_grayscale(frame) else "color"
                    out(f"camera {index} via {name:<16} : WORKING ({w}x{h}, {kind})")
                    found_any = True
                elif verdict == OPENED_NO_FRAMES:
                    out(f"camera {index} via {name:<16} : opens but delivers no frames "
                        f"({OPENED_NO_FRAMES}) - usually privacy settings or another app using it")
                else:
                    out(f"camera {index} via {name:<16} : only black frames ({verdict}) - lens covered or IR-only")
            except Exception as exc:
                out(f"camera {index} via {name:<16} : error {exc}")
            finally:
                if cap is not None:
                    cap.release()
    out("=" * 40)
    if not found_any:
        out("No working camera found. Check that:")
        out("  - no other app (Zoom/Teams/Camera) is using the webcam")
        out("  - " + PRIVACY_HINT)
        out("  - the USB camera is plugged in firmly")
        _write_report(lines)
        return 1
    out("At least one camera works. The app will pick it automatically.")
    _write_report(lines)
    return 0


def _write_report(lines: List[str]) -> None:
    """Diagnose-Camera.bat attaches this file to support requests (item 19)."""
    try:
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera-report.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\\n".join(lines) + "\\n")
        print(f"(report saved to {path})")
    except Exception:
        pass
