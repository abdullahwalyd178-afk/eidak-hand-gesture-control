# Eidak | إيدك — Hand Gesture PC Control

Control your computer with your hand through the webcam: move the mouse,
click, drag, scroll — plus a dedicated mode for video players
(play/pause, seek, volume, speed, fullscreen, close).

Everything runs **locally and offline**. No video or image ever leaves your PC.

---

## التثبيت (بالعربي)

1. نزّل الأداة: من صفحة المشروع اضغط **Code ← Download ZIP** وفك الضغط في أي مكان (يفضّل بارتيشن D).
2. لو Python مش متسطب عندك: نزّل **Python 3.11** من [python.org/downloads](https://www.python.org/downloads/) وحدّد خيار **"Add python.exe to PATH"** أثناء التثبيت.
3. افتح ملف **`Install-And-Run.bat`** بضغطتين. أول مرة هيجهّز كل حاجة لوحده، وبعدها هيشغّل الأداة على طول.
4. لو الكاميرا مشتغلتش: افتح **`Diagnose-Camera.bat`** وهو هيطبع تقرير كامل عن حالة كل كاميرا.

📖 **الدليل الكامل بالصور والجداول:** ملف `UserGuide-AR.pdf` جوه المشروع.

## Installation (English)

1. Download this project (**Code → Download ZIP**) and extract it anywhere.
2. Install **Python 3.11 or 3.12** from [python.org](https://www.python.org/downloads/) — tick **"Add python.exe to PATH"**.
3. Double-click **`Install-And-Run.bat`**. The first run installs dependencies; then the app starts.
4. Camera trouble? Run **`Diagnose-Camera.bat`** for a full camera report.

📖 Full manual: `UserGuide-EN.pdf` (English) and `UserGuide-AR.pdf` (العربية).

## Gestures — Mouse mode | وضع الماوس

| Gesture | الإشارة | Action |
|---|---|---|
| ☝️ Index finger up | صباع السبابة بس مرفوع | Move the cursor / تحريك الماوس |
| 🤏 Pinch thumb + index | قرصة الإبهام مع السبابة | Left click (hold = drag) / كليك شمال (استمرار = سحب) |
| 🤏 Pinch thumb + middle | قرصة الإبهام مع الوسطاني | Right click / كليك يمين |
| 🤏🤏 Two quick pinches | قرصتين ورا بعض | Double click / دبل كليك |
| ✌️ Index + middle, move up/down | صباعين وحرّك إيدك فوق/تحت | Scroll / سكرول |
| ✋ Open palm (hold) | كف مفتوح (ثبّته) | Pause / resume / إيقاف مؤقت واستئناف |

## Gestures — Video mode | وضع الفيديو

Press **M** to switch. | اضغط حرف **M** للتبديل.

| Gesture | الإشارة | Action |
|---|---|---|
| ✋ Open palm (hold) | كف مفتوح | Play / pause / تشغيل وإيقاف |
| 👉 Swipe right | مسح يمين | Forward 10s / تقديم |
| 👈 Swipe left | مسح شمال | Back 10s / ترجيع |
| ⬆️ Swipe up | مسح فوق | Volume up / تعلية الصوت |
| ⬇️ Swipe down | مسح تحت | Volume down / وطية الصوت |
| ✊ Fist (hold 1s) | قبضة (ثبّتها) | Close video/tab / قفل الفيديو |
| 🤟 3 fingers (hold) | 3 صوابع | Speed up / تسريع |
| 🖖 4 fingers no thumb (hold) | 4 صوابع من غير الإبهام | Speed down / تبطئة |
| 👍 Thumb up (hold) | إبهام لفوق | Fullscreen / ملء الشاشة |

## Keyboard | لوحة المفاتيح

**Q** quit · **M** switch mouse/video mode · **P** pause · **+ / −** cursor sensitivity

## Camera reliability | معالجة مشاكل الكاميرا

Built specifically to survive flaky cameras:

- **Auto-probing** of camera indices 0–4 and every Windows driver path (DirectShow, MediaFoundation) — it finds the working one itself.
- **Frame validation** — a camera that opens but sends black/empty frames is rejected.
- **Auto-reconnect** with backoff if the camera freezes or is unplugged mid-run; the app recovers alone when it comes back.
- **Low-light warning** on screen when the room is too dark for reliable tracking.
- **`Diagnose-Camera.bat`** — standalone report of every camera and driver, for troubleshooting.
- Settings (camera index, sensitivity, speeds…) live in `config.json` after the first run.

Emergency stop: slam the real mouse into any screen corner (PyAutoGUI fail-safe).

## Requirements | المتطلبات

- Windows 10/11 (works on Linux/macOS too) · Python 3.9–3.12 · any webcam
- `pip install -r requirements.txt` (done automatically by the .bat)
- Note: MediaPipe is pinned to `0.10.14` — newer versions removed the hand API this app uses.

## Privacy | الخصوصية

All processing happens on your device. The camera feed is never recorded,
uploaded or sent anywhere. No account, no internet needed after installation.

## Development

```bash
python test_gestures.py     # headless gesture-logic tests (no camera needed)
python hand_gesture_control.py --diagnose
python hand_gesture_control.py --mode media --camera 1 --sensitivity 1.6
```
