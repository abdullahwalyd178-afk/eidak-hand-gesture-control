# Migrating from legacy MediaPipe Hands to MediaPipe Tasks | خطة هجرة MediaPipe

Status: **prototype only** — `mediapipe_tasks_backend.py` exists on this
branch, is not imported by the app, and has never run against a real camera.

## Why migrate at all? | ليه نهاجر أصلًا؟

Eidak uses the legacy API:

```python
hands = mp.solutions.hands.Hands(...)   # hand_gesture_control.py
results = hands.process(rgb)
```

That API was removed from MediaPipe after **0.10.14**, so `requirements.txt`
pins `mediapipe==0.10.14` — which only supports **Python 3.9–3.12**. Every
future Python version, security fix and MediaPipe improvement is closed to
the project until the hand-tracking backend is replaced. This is the
project's biggest long-term risk; everything else is incremental.

## API differences (verified against mediapipe 0.10.14, which ships both APIs)

| Legacy (`mp.solutions`) | Tasks (`mediapipe.tasks.python.vision`) |
|---|---|
| Bundled model, no extra files | Needs a separate **`hand_landmarker.task`** model file (download, ship with the app, ~8 MB) |
| `hands.Hands(static_image_mode=False, max_num_hands, min_detection_confidence, min_tracking_confidence, model_complexity=0)` | `HandLandmarker.create_from_options(HandLandmarkerOptions(BaseOptions(model_asset_path=...), running_mode=VIDEO, num_hands, min_hand_detection_confidence, min_hand_presence_confidence, min_tracking_confidence))` |
| `hands.process(rgb_array)` — no timestamps | `detect_for_video(mp_image, timestamp_ms)` — timestamps must **strictly increase**; there is also `detect()` for single images and a `LIVE_STREAM` mode with a result callback |
| `results.multi_hand_landmarks[0].landmark` → points with `.x/.y/.z` | `result.hand_landmarks[0]` → `NormalizedLandmark(x, y, z, visibility, presence)` — same 21-point layout and normalized coordinates |
| `mp.solutions.drawing_utils` draws the overlay | No direct equivalent for the HUD overlay; drawing must be done manually (e.g. with OpenCV lines/circles over the 21 points, connections list is the same topology) |
| `model_complexity=0` picks the light model | Model choice = which `.task` file you ship (float16 = light); no complexity flag |

Config mapping: Eidak's `max_num_hands`, `detection_confidence` and
`tracking_confidence` carry over directly. `min_hand_presence_confidence`
is new; the prototype feeds it the detection confidence until real testing
suggests a better value.

## What the prototype does

`mediapipe_tasks_backend.HandLandmarkerBackend(cfg)` offers
`process(rgb, timestamp_ms) -> [(x, y, z), ...] | None` — the exact list
shape `GesturePipeline.process()` already consumes — plus `close()`.
Swapping it in would be a small, localized change in `run()` in
`hand_gesture_control.py` (construction + per-frame call + overlay drawing).

## What is NOT done | اللي لسه متعملش

- ❌ **No real-camera test.** Nothing here has seen a webcam, a real hand,
  or Windows. Gesture accuracy, latency and CPU use are all unknown.
- ❌ **No integration.** The app still uses the legacy API everywhere;
  the drawing overlay (`drawing_utils`) has no replacement written yet.
- ❌ **Model file distribution.** `hand_landmarker.task` is not in this
  repo; where to download it, its license, and how the installer/bat and
  the PyInstaller build should bundle it are undecided.
- ❌ **No accuracy comparison.** The Tasks model may not behave identically
  (landmark jitter, pinch distances); Eidak's thresholds in
  `DEFAULT_CONFIG` were tuned against the legacy model and may need retuning.
- ❌ **No performance numbers.** Legacy uses the light model deliberately
  (roughly half the CPU); the equivalent Tasks setup must be measured.

## Next steps | الخطوات الجاية

1. 👤 Download `hand_landmarker.task`, run the prototype side-by-side with
   the legacy backend on a real Windows PC + camera, compare stability.
2. Record CPU/FPS for both backends on a modest machine.
3. If accuracy holds: wire the backend into `run()` behind a config flag
   (e.g. `hand_backend: "legacy" | "tasks"`), keep legacy as fallback.
4. Write an OpenCV-based overlay to replace `drawing_utils`.
5. Retune thresholds if needed; run the full gesture suite plus a manual
   gesture checklist (see `docs/RELEASING.md` hardware list).
6. Only then: unpin mediapipe, raise the Python ceiling, and drop the
   legacy path in a following release.
