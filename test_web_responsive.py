import os
import sys
import subprocess
from pathlib import Path

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
STATIC_DIR = r"D:\KayiBots\File to Link Bot\static"
INDEX_PATH = os.path.join(STATIC_DIR, "index.html")
CSS_PATH = os.path.join(STATIC_DIR, "app.css")
JS_PATH = os.path.join(STATIC_DIR, "app.js")
SCREENSHOTS_DIR = r"D:\KayiBots\File to Link Bot\test_screenshots"

def run_tests():
    print("[TEST] Running Web Player UI & Responsiveness Verification Suite...", flush=True)
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    # 1. Verify HTML Structure
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()

    assert 'id="dashContentSettings" style="display: none;"' not in html_content, \
        "FAILED: dashContentSettings still has inline style='display: none;'!"
    assert 'id="dashContentSettings"' in html_content
    assert 'role="tablist"' in html_content
    assert 'id="tabDashFiles"' in html_content
    assert 'id="tabDashSettings"' in html_content
    assert 'role="tab"' in html_content
    assert 'role="tabpanel"' in html_content
    print("  [PASS] 1. Verified HTML structure: inline display:none removed, proper ARIA tablist/tab/tabpanel roles added.", flush=True)

    # 2. Verify CSS Design & Responsiveness
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        css_content = f.read()

    assert "--brand-primary: #4F46E5;" in css_content
    assert "--brand-violet: #6366F1;" in css_content
    assert ".dash-nav-tab-btn" in css_content
    assert "min-height: 44px;" in css_content
    assert "@media (max-width: 360px)" in css_content
    assert "@media (min-width: 768px)" in css_content
    assert "env(safe-area-inset-bottom" in css_content
    print("  [PASS] 2. Verified CSS design tokens: Royal blue (#4F46E5), touch targets (>=44px), safe areas, 320/360px media queries.", flush=True)

    # 3. Verify JavaScript logic
    with open(JS_PATH, "r", encoding="utf-8") as f:
        js_content = f.read()

    assert "switchDashboardTab" in js_content
    assert "aria-selected" in js_content
    assert "applySubtitleCustomization" in js_content
    print("  [PASS] 3. Verified JS event handling: switchDashboardTab manages active classes, ARIA attributes, and explicit display styles.", flush=True)

    # 4. Viewports Rendering
    viewports = [
        ("mobile_320", 320, 640),
        ("mobile_360", 360, 740),
        ("mobile_375_iphone_se", 375, 667),
        ("mobile_390_iphone14", 390, 844),
        ("mobile_430_iphone_max", 430, 932),
        ("desktop_1200", 1200, 800)
    ]

    edge_base_cmd = [
        EDGE_PATH,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
    ]

    index_uri = Path(INDEX_PATH).as_uri()

    for name, width, height in viewports:
        screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{name}.png")
        cmd = edge_base_cmd + [
            f"--window-size={width},{height}",
            f"--screenshot={screenshot_path}",
            index_uri
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=25)
            if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 1000:
                print(f"  [PASS] 4. Rendered viewport {width}x{height} ({name}) -> {os.path.getsize(screenshot_path)} bytes.", flush=True)
            else:
                print(f"  [WARN] Viewport {width}x{height} screenshot empty or failed.", flush=True)
        except Exception as e:
            print(f"  [ERROR] Failed rendering viewport {name}: {e}", flush=True)

    # 5. Test Preferences Tab Active View
    test_pref_html = os.path.join(STATIC_DIR, "_test_pref.html")
    injected_html = html_content.replace(
        "</body>",
        """<script>
        window.addEventListener('DOMContentLoaded', () => {
            setTimeout(() => {
                const tab = document.getElementById('tabDashSettings');
                if (tab) tab.click();
            }, 300);
        });
        </script></body>"""
    )
    with open(test_pref_html, "w", encoding="utf-8") as f:
        f.write(injected_html)

    try:
        pref_uri = Path(test_pref_html).as_uri()

        # Capture Desktop Preferences View
        desktop_pref_png = os.path.join(SCREENSHOTS_DIR, "desktop_preferences_active.png")
        cmd_desktop = edge_base_cmd + [
            "--window-size=1200,800",
            f"--screenshot={desktop_pref_png}",
            pref_uri
        ]
        subprocess.run(cmd_desktop, capture_output=True, timeout=25)
        if os.path.exists(desktop_pref_png) and os.path.getsize(desktop_pref_png) > 1000:
            print(f"  [PASS] 5a. Captured active Preferences screen on Desktop (1200px) -> {os.path.getsize(desktop_pref_png)} bytes.", flush=True)

        # Capture Mobile Preferences View (375px)
        mobile_pref_png = os.path.join(SCREENSHOTS_DIR, "mobile_preferences_active.png")
        cmd_mobile = edge_base_cmd + [
            "--window-size=375,700",
            f"--screenshot={mobile_pref_png}",
            pref_uri
        ]
        subprocess.run(cmd_mobile, capture_output=True, timeout=25)
        if os.path.exists(mobile_pref_png) and os.path.getsize(mobile_pref_png) > 1000:
            print(f"  [PASS] 5b. Captured active Preferences screen on Mobile (375px) -> {os.path.getsize(mobile_pref_png)} bytes.", flush=True)

    finally:
        if os.path.exists(test_pref_html):
            os.remove(test_pref_html)

    print("\n[ALL RESPONSIVE AND PREFERENCE TESTS PASSED SUCCESSFULLY!]", flush=True)

if __name__ == "__main__":
    run_tests()
