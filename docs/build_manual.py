#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Builds UserGuide-AR.pdf and UserGuide-EN.pdf (prebuilt copies live at the
repo root). Requires: pip install weasyprint. Downloads the Amiri font on
first run. You do NOT need this script to use Eidak - the PDFs are ready."""

import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT_DIR = os.path.join(HERE, "fonts")
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf"
FONT_BOLD_URL = "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Bold.ttf"


def ensure_fonts():
    os.makedirs(FONT_DIR, exist_ok=True)
    for url, name in ((FONT_URL, "Amiri-Regular.ttf"), (FONT_BOLD_URL, "Amiri-Bold.ttf")):
        path = os.path.join(FONT_DIR, name)
        if not os.path.exists(path):
            print("downloading", name)
            urllib.request.urlretrieve(url, path)


CSS = """
@font-face { font-family: Amiri; src: url('FONTPATH/Amiri-Regular.ttf'); }
@font-face { font-family: Amiri; src: url('FONTPATH/Amiri-Bold.ttf'); font-weight: bold; }
@page { size: A4; margin: 2cm 1.8cm; @bottom-center { content: counter(page); font-size: 9pt; color: #999; } }
body { font-family: Amiri, 'Noto Sans Arabic', sans-serif; font-size: 12.5pt; line-height: 1.75; color: #1c1c1c; }
body[dir=rtl] h1, body[dir=rtl] h2, body[dir=rtl] h3 { font-weight: bold; }
h1 { font-size: 24pt; color: #123f6d; border-bottom: 3px solid #123f6d; padding-bottom: 6px; }
h2 { font-size: 16pt; color: #123f6d; margin-top: 1.4em; }
table { width: 100%; border-collapse: collapse; margin: 0.6em 0; font-size: 11.5pt; }
th { background: #123f6d; color: #fff; padding: 6px 8px; }
td { border: 1px solid #b9c6d3; padding: 5px 8px; }
tr:nth-child(even) td { background: #eef3f8; }
.tip { background: #fff7e0; border: 1px solid #e8c95c; border-radius: 6px; padding: 8px 12px; margin: 0.8em 0; }
.warn { background: #fdecec; border: 1px solid #e07b7b; border-radius: 6px; padding: 8px 12px; margin: 0.8em 0; }
.ok { background: #e9f7ee; border: 1px solid #6fbf8a; border-radius: 6px; padding: 8px 12px; margin: 0.8em 0; }
code, .k { font-family: monospace; background: #eef0f2; border-radius: 4px; padding: 1px 5px; font-size: 10.5pt; }
.g { font-size: 12.5pt; }
img.e { height: 13pt; vertical-align: -2pt; }
ul { margin: 0.3em 0; }
"""

AR_BODY = """
<h1>Ø¥ÙØ¯Ù â Ø¯ÙÙÙ Ø§ÙØ§Ø³ØªØ®Ø¯Ø§Ù Ø§ÙÙØ§ÙÙ</h1>
<p><b>Ø¥ÙØ¯Ù</b> Ø£Ø¯Ø§Ø© Ø¨ØªØ®ÙÙÙ ØªØªØ­ÙÙ ÙÙ Ø§ÙÙÙØ¨ÙÙØªØ± Ø¨Ø¥Ø´Ø§Ø±Ø§Øª Ø¥ÙØ¯Ù ÙØ¯Ø§Ù Ø§ÙÙØ§ÙÙØ±Ø§: ØªØ­Ø±Ù Ø§ÙÙØ§ÙØ³Ø ØªØ¹ÙÙ ÙÙÙÙØ ØªØ³Ø­Ø¨ ÙØªØ³ÙØ±ÙÙØ ÙÙÙÙØ§ ÙØ¶Ø¹ ÙØ®ØµÙØµ ÙÙØªØ­ÙÙ ÙÙ Ø§ÙÙÙØ¯ÙÙÙØ§Øª. ÙÙ Ø§ÙÙØ¹Ø§ÙØ¬Ø© Ø¹ÙÙ Ø¬ÙØ§Ø²ÙØ ÙÙÙÙØ´ Ø£Ù ØµÙØ±Ø© Ø£Ù ÙÙØ¯ÙÙ Ø¨ÙØªØ¨Ø¹Øª ÙØ£Ù ÙÙØ§Ù.</p>

<h2>Ù¡ â Ø§ÙØªØ«Ø¨ÙØª Ø®Ø·ÙØ© Ø¨Ø®Ø·ÙØ©</h2>
<table>
<tr><th>Ø§ÙØ®Ø·ÙØ©</th><th>ÙØªØ¹ÙÙ Ø¥ÙÙ</th></tr>
<tr><td>Ù¡</td><td>ÙØ²ÙÙ Ø§ÙÙØ´Ø±ÙØ¹ ÙÙ GitHub: Ø²Ø±Ø§Ø± <span class="k">Code</span> Ø«Ù <span class="k">Download ZIP</span>Ø ÙÙÙ Ø§ÙØ¶ØºØ· ÙÙ Ø£Ù ÙÙØ§Ù.</td></tr>
<tr><td>Ù¢</td><td>ÙÙ Ø¨Ø§ÙØ«ÙÙ ÙØ´ Ø¹ÙØ¯Ù: ÙØ²ÙÙ <b>Python 3.11</b> ÙÙ <span class="k">python.org/downloads</span> â ÙÙÙÙ Ø¬Ø¯ÙØ§ ØªØ­Ø¯Ø¯ ÙØ±Ø¨Ø¹ <b>Add python.exe to PATH</b> Ø£Ø«ÙØ§Ø¡ Ø§ÙØªØ«Ø¨ÙØª.</td></tr>
<tr><td>Ù£</td><td>Ø§ÙØªØ­ ÙÙÙ <span class="k">Install-And-Run.bat</span> Ø¨Ø¶ØºØ·ØªÙÙ. Ø£ÙÙ ØªØ´ØºÙÙØ© Ø¨ÙÙØ²ÙÙ Ø§ÙÙØªØ·ÙØ¨Ø§Øª ÙÙØ­Ø¯Ù (ÙØ­ØªØ§Ø¬ ÙØª ÙØ±Ø© ÙØ§Ø­Ø¯Ø© Ø¨Ø³)Ø ÙØ¨Ø¹Ø¯ÙØ§ Ø§ÙØ£Ø¯Ø§Ø© ØªØ´ØªØºÙ ÙÙØ±ÙØ§.</td></tr>
<tr><td>Ù¤</td><td>ÙØªÙØªØ­ ÙØ§ÙØ°Ø© ÙÙÙØ§ ØµÙØ±Ø© Ø§ÙÙØ§ÙÙØ±Ø§. ÙØ±ÙÙ Ø¥ÙØ¯Ù ÙÙÙØ§ÙÙØ±Ø§ ÙØ§Ø¨Ø¯Ø£.</td></tr>
</table>
<div class="tip">ÙÙ Ø§ÙÙØ§ÙÙØ±Ø§ ÙØ§ ÙØªØ­ØªØ´Ø Ø´ØºÙÙ <span class="k">Diagnose-Camera.bat</span> â ÙÙØ·ÙØ¹ ØªÙØ±ÙØ± Ø¨ÙÙ ÙØ§ÙÙØ±Ø§ ÙÙÙ ØªØ¹Ø±ÙÙ ÙØ¥ÙÙ Ø§ÙÙÙ Ø´ØºØ§Ù ÙØ¥ÙÙ Ø§ÙÙÙ ÙØ£.</div>

<h2>Ù¢ â Ø¥Ø´Ø§Ø±Ø§Øª ÙØ¶Ø¹ Ø§ÙÙØ§ÙØ³</h2>
<table>
<tr><th>Ø§ÙØ¥Ø´Ø§Ø±Ø©</th><th>Ø§ÙÙØ¸ÙÙØ©</th><th>ÙÙØ§Ø­Ø¸Ø§Øª</th></tr>
<tr><td class="g"><img class='e' src='emoji/261d.png' alt=''> Ø³Ø¨Ø§Ø¨Ø© Ø¨Ø³ ÙØ±ÙÙØ¹</td><td>ØªØ­Ø±ÙÙ Ø§ÙÙØ§ÙØ³</td><td>Ø­Ø±ÙÙ Ø¥ÙØ¯ÙØ Ø§ÙÙØ¤Ø´Ø± ÙÙØªØ¨Ø¹ÙØ§ Ø¨ÙØ¹ÙÙØ©</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f90f.png' alt=''> ÙØ±ØµØ© Ø¥Ø¨ÙØ§Ù + Ø³Ø¨Ø§Ø¨Ø©</td><td>ÙÙÙÙ Ø´ÙØ§Ù</td><td>ÙØ±ØµØ© Ø³Ø±ÙØ¹Ø©</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f90f.png' alt=''> ÙØ±ØµØ© ÙØ³ØªÙØ±Ø©</td><td>Ø³Ø­Ø¨ ÙØ¥ÙÙØ§Øª</td><td>Ø«Ø¨ÙØª Ø§ÙÙØ±ØµØ© ÙØ­Ø±ÙÙØ ÙØ§ÙØªÙ ÙÙØ¥ÙÙØ§Øª</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f90f.png' alt=''> Ø¥Ø¨ÙØ§Ù + ÙØ³Ø·Ø§ÙÙ</td><td>ÙÙÙÙ ÙÙÙÙ</td><td>ÙØ±ØµØ© Ø³Ø±ÙØ¹Ø©</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f90f.png' alt=''><img class='e' src='emoji/1f90f.png' alt=''> ÙØ±ØµØªÙÙ Ø³Ø±ÙØ¹ØªÙÙ</td><td>Ø¯Ø¨Ù ÙÙÙÙ</td><td>ÙØ±Ø§ Ø¨Ø¹Ø¶ ÙÙ Ø£ÙÙ ÙÙ ÙØµ Ø«Ø§ÙÙØ© ØªÙØ±ÙØ¨ÙØ§</td></tr>
<tr><td class="g"><img class='e' src='emoji/270c.png' alt=''> Ø³Ø¨Ø§Ø¨Ø© + ÙØ³Ø·Ø§ÙÙ</td><td>Ø³ÙØ±ÙÙ</td><td>Ø­Ø±ÙÙ Ø¥ÙØ¯Ù ÙÙÙ Ø£Ù ØªØ­Øª</td></tr>
<tr><td class="g"><img class='e' src='emoji/270b.png' alt=''> ÙÙ ÙÙØªÙØ­ (Ø«Ø¨ÙØªÙ)</td><td>Ø¥ÙÙØ§Ù ÙØ¤ÙØª / Ø§Ø³ØªØ¦ÙØ§Ù</td><td>Ø£ÙØ§Ù: ÙØ¬ÙÙØ¯ Ø§ÙØªØ­ÙÙ ÙØ­Ø¯ ÙØ§ ØªØ±Ø¬Ø¹Ù</td></tr>
</table>

<h2>Ù£ â Ø¥Ø´Ø§Ø±Ø§Øª ÙØ¶Ø¹ Ø§ÙÙÙØ¯ÙÙ</h2>
<p>Ø§Ø¶ØºØ· Ø­Ø±Ù <span class="k">M</span> ÙÙ Ø§ÙÙÙØ¨ÙØ±Ø¯ ÙÙØªØ¨Ø¯ÙÙ Ø¨ÙÙ ÙØ¶Ø¹ Ø§ÙÙØ§ÙØ³ ÙÙØ¶Ø¹ Ø§ÙÙÙØ¯ÙÙ. Ø§ÙÙØ¶Ø¹ Ø§ÙØ­Ø§ÙÙ ÙÙØªÙØ¨ ÙÙÙ ÙÙ ÙØ§ÙØ°Ø© Ø§ÙØ£Ø¯Ø§Ø©. Ø§ÙØ¥Ø´Ø§Ø±Ø§Øª Ø¯Ù Ø´ØºØ§ÙØ© ÙØ¹ ÙÙØªÙÙØ¨ ÙØ£ØºÙØ¨ Ø§ÙÙØ´ØºÙÙØ§Øª:</p>
<table>
<tr><th>Ø§ÙØ¥Ø´Ø§Ø±Ø©</th><th>Ø§ÙÙØ¸ÙÙØ©</th></tr>
<tr><td class="g"><img class='e' src='emoji/270b.png' alt=''> ÙÙ ÙÙØªÙØ­ (Ø«Ø¨ÙØªÙ)</td><td>ØªØ´ØºÙÙ / Ø¥ÙÙØ§Ù Ø§ÙÙÙØ¯ÙÙ</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f449.png' alt=''> ÙØ³Ø­ Ø³Ø±ÙØ¹ ÙÙÙÙ</td><td>ØªÙØ¯ÙÙ Ø§ÙÙÙØ¯ÙÙ (ÙÙØ¯Ø§Ø± Ø§ÙØ®Ø·ÙØ© Ø­Ø³Ø¨ Ø§ÙÙØ´ØºÙÙ)</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f448.png' alt=''> ÙØ³Ø­ Ø³Ø±ÙØ¹ Ø´ÙØ§Ù</td><td>ØªØ±Ø¬ÙØ¹ Ø§ÙÙÙØ¯ÙÙ (ÙÙØ¯Ø§Ø± Ø§ÙØ®Ø·ÙØ© Ø­Ø³Ø¨ Ø§ÙÙØ´ØºÙÙ)</td></tr>
<tr><td class="g"><img class='e' src='emoji/2b06.png' alt=''> ÙØ³Ø­ ÙÙÙÙ</td><td>ØªØ¹ÙÙØ© Ø§ÙØµÙØª</td></tr>
<tr><td class="g"><img class='e' src='emoji/2b07.png' alt=''> ÙØ³Ø­ ÙØªØ­Øª</td><td>ÙØ·ÙØ© Ø§ÙØµÙØª</td></tr>
<tr><td class="g"><img class='e' src='emoji/270a.png' alt=''> ÙØ¨Ø¶Ø© ÙØ±ØªÙÙ ÙØ±Ø§ Ø¨Ø¹Ø¶ (ÙÙ ÙØ±Ø© Ø«Ø§ÙÙØ©: Ø§ÙØ£ÙÙÙ ØªØ¬ÙÙØ² ÙØ§ÙØªØ§ÙÙØ© ØªØ¤ÙØ¯ Ø§ÙÙÙÙ)</td><td>ÙÙÙ Ø§ÙÙÙØ¯ÙÙ / Ø§ÙØªØ§Ø¨</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f919.png' alt=''> Ù£ ØµÙØ§Ø¨Ø¹ (Ø«Ø¨ÙØªÙÙ)</td><td>ØªØ³Ø±ÙØ¹ Ø§ÙÙÙØ¯ÙÙ</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f596.png' alt=''> Ù¤ ØµÙØ§Ø¨Ø¹ ÙÙ ØºÙØ± Ø§ÙØ¥Ø¨ÙØ§Ù</td><td>ØªØ¨Ø·Ø¦Ø© Ø§ÙÙÙØ¯ÙÙ</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f44d.png' alt=''> Ø¥Ø¨ÙØ§Ù ÙÙÙÙ (Ø«Ø¨ÙØªÙ)</td><td>ÙÙØ¡ Ø§ÙØ´Ø§Ø´Ø©</td></tr>
</table>

<h2>Ù¤ â Ø§ÙÙÙØ¨ÙØ±Ø¯</h2>
<ul>
<li><span class="k">Q</span> ÙÙÙ Ø§ÙØ£Ø¯Ø§Ø©</li>
<li><span class="k">M</span> Ø§ÙØªØ¨Ø¯ÙÙ Ø¨ÙÙ ÙØ¶Ø¹ Ø§ÙÙØ§ÙØ³ ÙÙØ¶Ø¹ Ø§ÙÙÙØ¯ÙÙ</li>
<li><span class="k">P</span> Ø¥ÙÙØ§Ù ÙØ¤ÙØª / Ø§Ø³ØªØ¦ÙØ§Ù</li>
<li><span class="k">+</span> Ù <span class="k">-</span> Ø²ÙØ§Ø¯Ø© Ø£Ù ØªÙÙÙÙ Ø­Ø³Ø§Ø³ÙØ© Ø§ÙÙØ¤Ø´Ø±</li>
</ul>

<h2>Ù¥ â ÙÙ Ø§ÙÙØ§ÙÙØ±Ø§ Ø¹ÙÙØª ÙØ´Ø§ÙÙ</h2>
<p>Ø§ÙØ£Ø¯Ø§Ø© ÙØªØµÙÙØ© Ø£ØµÙÙØ§ Ø¹Ø´Ø§Ù ØªØªØ¹Ø§ÙÙ ÙØ¹ Ø§ÙÙØ§ÙÙØ±Ø§Øª Ø§ÙÙØ´Ø§ØºØ¨Ø©:</p>
<ul>
<li><b>Ø¨ØªØ¯ÙØ± ÙÙØ­Ø¯ÙØ§:</b> Ø¨ØªØ¬Ø±Ø¨ ÙÙ Ø§ÙÙØ§ÙÙØ±Ø§Øª (ÙÙ Ù  ÙÙ Ù¤) ÙÙÙ ØªØ¹Ø±ÙÙØ§Øª ÙÙÙØ¯ÙØ² (DirectShow ÙMediaFoundation) ÙØªØ®ØªØ§Ø± Ø§ÙÙÙ Ø¨ÙØ´ØªØºÙ ÙØ¹ÙÙØ§.</li>
<li><b>Ø¨ØªØªØ£ÙØ¯ ÙÙ Ø§ÙØµÙØ±Ø©:</b> Ø£Ù ÙØ§ÙÙØ±Ø§ Ø¨ØªÙØªØ­ Ø¨Ø³ Ø¨ØªØ¨Ø¹Øª ÙØ±ÙÙØ§Øª ÙØ§Ø¶ÙØ© Ø£Ù Ø³ÙØ¯Ø§ Ø¨ØªØ±ÙØ¶ÙØ§ ÙØªÙÙÙ Ø¨Ø­Ø«.</li>
<li><b>Ø¨ØªØ±Ø¬Ø¹ ÙÙØ­Ø¯ÙØ§:</b> ÙÙ Ø§ÙÙØ§ÙÙØ±Ø§ Ø¹ÙÙÙØª Ø£Ù Ø§ØªÙØµÙØª ÙÙ Ø§ÙÙØµØ Ø§ÙØ£Ø¯Ø§Ø© Ø¨ØªØ¹ÙÙ Ø¥Ø¹Ø§Ø¯Ø© Ø§ØªØµØ§Ù ØªÙÙØ§Ø¦ÙØ© ÙØªØ±Ø¬Ø¹ ØªØ´ØªØºÙ ÙÙØ§ Ø§ÙÙØ§ÙÙØ±Ø§ ØªØ±Ø¬Ø¹.</li>
<li><b>ØªØ­Ø°ÙØ± Ø§ÙØ¥Ø¶Ø§Ø¡Ø©:</b> ÙÙ Ø§ÙØ£ÙØ¶Ø© Ø¶ÙÙØ© ÙØ§ÙØªØªØ¨Ø¹ ÙÙØ¨ÙØ¸Ø ÙØªØ´ÙÙ ØªÙØ¨ÙÙ Ø¹ÙÙ Ø§ÙØ´Ø§Ø´Ø©.</li>
</ul>
<div class="warn">ÙÙ Ø§ÙÙØ§ÙÙØ±Ø§ Ø±Ø§ÙØ¶Ø© Ø®Ø§ÙØµ: Ø§ØªØ£ÙØ¯ Ø¥Ù ÙÙÙØ´ Ø¨Ø±ÙØ§ÙØ¬ ØªØ§ÙÙ ÙØ§ÙÙÙØ§ (Ø²ÙÙÙ / ØªÙÙØ² / ØªØ·Ø¨ÙÙ Ø§ÙÙØ§ÙÙØ±Ø§)Ø ÙÙÙ Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª ÙÙÙØ¯ÙØ²: <span class="k">Settings â Privacy â Camera</span> ÙÙØ¹ÙÙ Ø§ÙØ³ÙØ§Ø­ ÙØªØ·Ø¨ÙÙØ§Øª Ø³Ø·Ø­ Ø§ÙÙÙØªØ¨.</div>
<div class="tip">ÙÙ Ø¹ÙØ¯Ù Ø£ÙØªØ± ÙÙ ÙØ§ÙÙØ±Ø§ ÙØ¹Ø§ÙØ² ØªØ­Ø¯Ø¯ ÙØ§Ø­Ø¯Ø©: Ø¹Ø¯ÙÙ <span class="k">camera_index</span> ÙÙ ÙÙÙ <span class="k">config.json</span> Ø§ÙÙÙ Ø¨ÙØªØ¹ÙÙ Ø¨Ø¹Ø¯ Ø£ÙÙ ØªØ´ØºÙÙØ©Ø Ø£Ù Ø´ØºÙÙ: <span class="k">python hand_gesture_control.py --camera 1</span></div>

<h2>Ù¦ â Ø§ÙØ¥Ø¹Ø¯Ø§Ø¯Ø§Øª (config.json)</h2>
<p>Ø¨Ø¹Ø¯ Ø£ÙÙ ØªØ´ØºÙÙØ© ÙØªÙØ§ÙÙ ÙÙÙ <span class="k">config.json</span> Ø¬ÙØ¨ Ø§ÙØ£Ø¯Ø§Ø©Ø ÙÙÙ ÙÙ Ø§ÙØ¥Ø¹Ø¯Ø§Ø¯Ø§Øª: Ø±ÙÙ Ø§ÙÙØ§ÙÙØ±Ø§Ø Ø§ÙØ­Ø³Ø§Ø³ÙØ© <span class="k">sensitivity</span>Ø ÙØ¹ÙÙØ© Ø§ÙØ­Ø±ÙØ© <span class="k">smoothing</span>Ø Ø³Ø±Ø¹Ø© Ø§ÙØ³ÙØ±ÙÙØ ÙØ¹ØªØ¨Ø§Øª Ø§ÙØ¥Ø´Ø§Ø±Ø§Øª. Ø¹Ø¯ÙÙ Ø£Ù ÙÙÙØ© ÙØ§Ø­ÙØ¸Ø ÙØ´ØºÙÙ Ø§ÙØ£Ø¯Ø§Ø© ÙÙ ØªØ§ÙÙ.</p>

<h2>Ù§ â Ø£ÙØ§Ù ÙØ®ØµÙØµÙØ©</h2>
<ul>
<li>ÙÙ Ø§ÙÙØ¹Ø§ÙØ¬Ø© Ø¹ÙÙ Ø¬ÙØ§Ø²Ù Ø£ÙÙÙØ§ÙÙ â ÙÙÙØ´ Ø£Ù ØµÙØ±Ø© Ø¨ØªØªØ³Ø¬Ù Ø£Ù Ø¨ØªØªØ¨Ø¹Øª.</li>
<li>Ø¥ÙÙØ§Ù Ø·ÙØ§Ø±Ø¦: Ø­Ø±ÙÙ Ø§ÙÙØ§ÙØ³ Ø§ÙØ­ÙÙÙÙ ÙØ£Ù Ø±ÙÙ ÙÙ Ø£Ø±ÙØ§Ù Ø§ÙØ´Ø§Ø´Ø©Ø Ø§ÙØ£Ø¯Ø§Ø© ÙØªÙÙÙ ÙÙØ±ÙØ§.</li>
<li>Ø§ÙØ¥Ø´Ø§Ø±Ø© <img class='e' src='emoji/270b.png' alt=''> (ÙÙ ÙÙØªÙØ­) ØªÙÙÙ Ø§ÙØªØ­ÙÙ ÙÙ Ø£Ù ÙÙØª.</li>
</ul>
"""

EN_BODY = """
<h1>Eidak â Full User Guide</h1>
<p><b>Eidak</b> ("your hand") lets you control your computer with hand gestures in front of the webcam: move the mouse, click, drag and scroll, plus a dedicated mode for video players. All processing is local and offline; no image or video ever leaves your PC.</p>

<h2>1 â Installation</h2>
<table>
<tr><th>Step</th><th>What to do</th></tr>
<tr><td>1</td><td>Download the project from GitHub: <span class="k">Code</span> â <span class="k">Download ZIP</span>, and extract it anywhere.</td></tr>
<tr><td>2</td><td>If you don't have Python: install <b>Python 3.11</b> from <span class="k">python.org/downloads</span> and tick <b>"Add python.exe to PATH"</b>.</td></tr>
<tr><td>3</td><td>Double-click <span class="k">Install-And-Run.bat</span>. The first run installs everything (needs internet once), then the app starts.</td></tr>
<tr><td>4</td><td>A camera window opens. Show your hand and go.</td></tr>
</table>
<div class="tip">Camera not opening? Run <span class="k">Diagnose-Camera.bat</span> for a full report of every camera and driver.</div>

<h2>2 â Mouse mode gestures</h2>
<table>
<tr><th>Gesture</th><th>Action</th><th>Notes</th></tr>
<tr><td class="g"><img class='e' src='emoji/261d.png' alt=''> Index finger up</td><td>Move cursor</td><td>Smoothed pointer follows your fingertip</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f90f.png' alt=''> Pinch thumb + index</td><td>Left click</td><td>Quick pinch</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f90f.png' alt=''> Hold the pinch</td><td>Drag &amp; drop</td><td>Hold, move, release to drop</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f90f.png' alt=''> Pinch thumb + middle</td><td>Right click</td><td>Quick pinch</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f90f.png' alt=''><img class='e' src='emoji/1f90f.png' alt=''> Two quick pinches</td><td>Double click</td><td>Within ~0.4 s</td></tr>
<tr><td class="g"><img class='e' src='emoji/270c.png' alt=''> Index + middle up</td><td>Scroll</td><td>Move your hand up / down</td></tr>
<tr><td class="g"><img class='e' src='emoji/270b.png' alt=''> Open palm (hold)</td><td>Pause / resume</td><td>Safety freeze</td></tr>
</table>

<h2>3 â Video mode gestures</h2>
<p>Press <span class="k">M</span> to switch between mouse and video mode; the active mode is shown at the top of the window. These work with YouTube and most players:</p>
<table>
<tr><th>Gesture</th><th>Action</th></tr>
<tr><td class="g"><img class='e' src='emoji/270b.png' alt=''> Open palm (hold)</td><td>Play / pause</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f449.png' alt=''> Quick swipe right</td><td>Seek forward (step depends on the player)</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f448.png' alt=''> Quick swipe left</td><td>Seek back (step depends on the player)</td></tr>
<tr><td class="g"><img class='e' src='emoji/2b06.png' alt=''> Swipe up</td><td>Volume up</td></tr>
<tr><td class="g"><img class='e' src='emoji/2b07.png' alt=''> Swipe down</td><td>Volume down</td></tr>
<tr><td class="g"><img class='e' src='emoji/270a.png' alt=''> Fist twice in a row (hold 1 s each: first arms, second confirms)</td><td>Close video / tab</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f919.png' alt=''> 3 fingers (hold)</td><td>Speed up</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f596.png' alt=''> 4 fingers, no thumb</td><td>Speed down</td></tr>
<tr><td class="g"><img class='e' src='emoji/1f44d.png' alt=''> Thumb up (hold)</td><td>Fullscreen</td></tr>
</table>

<h2>4 â Keyboard</h2>
<ul>
<li><span class="k">Q</span> quit</li>
<li><span class="k">M</span> switch mouse / video mode</li>
<li><span class="k">P</span> pause / resume</li>
<li><span class="k">+</span> / <span class="k">-</span> cursor sensitivity</li>
</ul>

<h2>5 â Camera problems</h2>
<p>Eidak is built to survive flaky cameras:</p>
<ul>
<li><b>Auto-probing:</b> tries camera indices 0â4 and every Windows driver path (DirectShow, MediaFoundation) and picks the one that actually works.</li>
<li><b>Frame validation:</b> a camera that opens but delivers black or empty frames is rejected.</li>
<li><b>Auto-reconnect:</b> if the camera freezes or is unplugged mid-run, Eidak reconnects by itself and resumes when it is back.</li>
<li><b>Low-light warning</b> on screen when the room is too dark for reliable tracking.</li>
</ul>
<div class="warn">If the camera refuses to open: make sure no other app is using it (Zoom / Teams / Camera), and in Windows: <span class="k">Settings â Privacy â Camera</span>, allow desktop apps.</div>
<div class="tip">Multiple cameras? Set <span class="k">camera_index</span> in <span class="k">config.json</span> (created after the first run) or launch with <span class="k">python hand_gesture_control.py --camera 1</span>.</div>

<h2>6 â Settings (config.json)</h2>
<p>After the first run, <span class="k">config.json</span> sits next to the app: camera index, <span class="k">sensitivity</span>, <span class="k">smoothing</span>, scroll speed and gesture thresholds. Edit, save, relaunch.</p>

<h2>7 â Safety &amp; privacy</h2>
<ul>
<li>Everything is processed on your device, offline. Nothing is recorded or uploaded.</li>
<li>Emergency stop: slam the physical mouse into any screen corner and the app quits.</li>
<li>The <img class='e' src='emoji/270b.png' alt=''> open-palm gesture freezes control at any time.</li>
</ul>
"""


def build():
    from weasyprint import HTML

    ensure_fonts()
    css = CSS.replace("FONTPATH", "fonts")
    for name, body, direction, lang in (
        ("UserGuide-AR.pdf", AR_BODY, "rtl", "ar"),
        ("UserGuide-EN.pdf", EN_BODY, "ltr", "en"),
    ):
        html = (
            f"<html lang='{lang}'><head><meta charset='utf-8'>"
            f"<style>{css}</style></head><body dir='{direction}'>{body}</body></html>"
        )
        out = os.path.join(ROOT, name)
        HTML(string=html, base_url=HERE).write_pdf(out)
        print("wrote", out)


if __name__ == "__main__":
    build()
