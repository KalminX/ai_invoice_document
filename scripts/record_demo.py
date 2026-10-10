import os
import time
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8008"
OUTPUT_DIR = Path("/Users/kalmin/projects/ai_invoice_document/recordings")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_VIDEO_DIR = OUTPUT_DIR / "raw_video"
RAW_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
FINAL_VIDEO_PATH = OUTPUT_DIR / "ai_invoice_pipeline_demo.mp4"

CURSOR_INJECTION_JS = """
(() => {
  function ensureCursor() {
    let cursor = document.getElementById('playwright-custom-cursor');
    if (!cursor) {
      cursor = document.createElement('div');
      cursor.id = 'playwright-custom-cursor';
      cursor.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 24px;
        height: 24px;
        pointer-events: none;
        z-index: 2147483647;
        transform: translate(-2px, -2px);
        transition: transform 0.04s ease-out;
      `;
      cursor.innerHTML = `
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="filter: drop-shadow(0 2px 5px rgba(0,0,0,0.5));">
          <path d="M5.5 3.5L18.5 12L12 13.5L9.5 20.5L5.5 3.5Z" fill="#2563eb" stroke="#ffffff" stroke-width="2.2" stroke-linejoin="round"/>
        </svg>
      `;
      document.documentElement.appendChild(cursor);
    }
  }

  window.moveCustomCursor = (x, y) => {
    ensureCursor();
    const cursor = document.getElementById('playwright-custom-cursor');
    if (cursor) {
      cursor.style.left = `${x}px`;
      cursor.style.top = `${y}px`;
    }
  };

  window.animateClickRipple = (x, y) => {
    const ripple = document.createElement('div');
    ripple.style.cssText = `
      position: fixed;
      left: ${x}px;
      top: ${y}px;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: rgba(37, 99, 235, 0.6);
      transform: translate(-50%, -50%) scale(1);
      pointer-events: none;
      z-index: 2147483646;
      transition: all 0.4s cubic-bezier(0.1, 0.8, 0.3, 1);
    `;
    document.documentElement.appendChild(ripple);
    requestAnimationFrame(() => {
      ripple.style.transform = 'translate(-50%, -50%) scale(4.5)';
      ripple.style.opacity = '0';
    });
    setTimeout(() => ripple.remove(), 450);
  };

  document.addEventListener('DOMContentLoaded', ensureCursor);
  ensureCursor();
})();
"""


def safe_eval(page, js_code):
    try:
        return page.evaluate(js_code)
    except Exception:
        return None


def smooth_move(page, start_x, start_y, end_x, end_y, steps=16, duration=0.28):
    """Smooth cubic bezier interpolation for natural cursor movement."""
    ctrl_x = (start_x + end_x) / 2 + (start_y - end_y) * 0.1
    ctrl_y = (start_y + end_y) / 2 + (end_x - start_x) * 0.1

    for i in range(1, steps + 1):
        t = i / steps
        x = (1 - t)**2 * start_x + 2 * (1 - t) * t * ctrl_x + t**2 * end_x
        y = (1 - t)**2 * start_y + 2 * (1 - t) * t * ctrl_y + t**2 * end_y
        try:
            page.mouse.move(x, y)
            safe_eval(page, f"window.moveCustomCursor && window.moveCustomCursor({x}, {y})")
        except Exception:
            pass
        time.sleep(duration / steps)


def click_element(page, selector, current_pos, offset_x=0, offset_y=0, delay_after=0.35):
    """Smoothly moves, triggers ripple effect, and clicks target."""
    loc = page.locator(selector).first
    loc.wait_for(state="visible", timeout=8000)
    box = loc.bounding_box()
    if not box:
        return current_pos

    target_x = box['x'] + box['width'] / 2 + offset_x
    target_y = box['y'] + box['height'] / 2 + offset_y

    smooth_move(page, current_pos[0], current_pos[1], target_x, target_y)
    safe_eval(page, f"window.animateClickRipple && window.animateClickRipple({target_x}, {target_y})")
    page.mouse.click(target_x, target_y)
    time.sleep(delay_after)
    return (target_x, target_y)


def type_text(page, selector, text, current_pos, clear_first=True, typing_speed=0.025):
    """Moves to input field, focuses it, and types with realistic speed."""
    current_pos = click_element(page, selector, current_pos, delay_after=0.15)
    if clear_first:
        page.keyboard.press("Meta+A")
        page.keyboard.press("Backspace")
        time.sleep(0.08)

    for char in text:
        page.keyboard.type(char)
        time.sleep(typing_speed)

    time.sleep(0.18)
    return current_pos


def run_recording():
    print("🎬 Starting Playwright recording session (1280x720 30FPS)...")

    for old_vid in RAW_VIDEO_DIR.glob("*.*"):
        try:
            old_vid.unlink()
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--force-device-scale-factor=1",
                "--disable-web-security"
            ]
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(RAW_VIDEO_DIR),
            record_video_size={"width": 1280, "height": 720}
        )

        context.add_init_script(CURSOR_INJECTION_JS)
        page = context.new_page()
        cursor_pos = (640, 360)

        # -----------------------------------------------------------------
        # SCENE 1: Sign-In Screen & Persona Authentication
        # -----------------------------------------------------------------
        print("  ▶ Scene 1: Sign-in & Persona Authentication")
        page.goto(f"{BASE_URL}/login/")
        page.wait_for_load_state("networkidle")
        time.sleep(0.8)

        # Select Alex Rivera (AP Specialist) persona
        cursor_pos = click_element(page, ".demo-user-btn:has-text('Alex Rivera')", cursor_pos, delay_after=0.5)
        
        # Click Sign In button
        cursor_pos = click_element(page, "button[type='submit']:has-text('Sign In')", cursor_pos, delay_after=1.0)
        page.wait_for_load_state("networkidle")

        # -----------------------------------------------------------------
        # SCENE 2: Executive Dashboard & KPI Metrics
        # -----------------------------------------------------------------
        print("  ▶ Scene 2: Dashboard Overview & Metric Ticker Animations")
        time.sleep(1.0)

        # Hover over KPI metric cards
        cards = page.locator(".metric-card").all()
        for card in cards[:3]:
            box = card.bounding_box()
            if box:
                smooth_move(page, cursor_pos[0], cursor_pos[1], box['x'] + box['width']/2, box['y'] + box['height']/2, steps=12, duration=0.2)
                cursor_pos = (box['x'] + box['width']/2, box['y'] + box['height']/2)
                time.sleep(0.25)

        # Scroll down slightly to view recent invoices and audit stream
        page.mouse.wheel(0, 200)
        time.sleep(0.6)
        page.mouse.wheel(0, -200)
        time.sleep(0.4)

        # -----------------------------------------------------------------
        # SCENE 3: Document Intake (Upload New Invoice)
        # -----------------------------------------------------------------
        print("  ▶ Scene 3: Document Intake & File Upload")
        page.goto(f"{BASE_URL}/documents/upload/")
        page.wait_for_load_state("networkidle")
        time.sleep(0.6)

        fixture_path = "/Users/kalmin/projects/ai_invoice_document/media/fixtures/acme_cloud_invoice.pdf"
        if os.path.exists(fixture_path):
            drop_loc = page.locator("#upload-dropzone").first
            drop_loc.wait_for(state="visible", timeout=8000)
            drop_box = drop_loc.bounding_box()
            if drop_box:
                smooth_move(page, cursor_pos[0], cursor_pos[1], drop_box['x'] + drop_box['width']/2, drop_box['y'] + drop_box['height']/2, steps=12, duration=0.25)
                cursor_pos = (drop_box['x'] + drop_box['width']/2, drop_box['y'] + drop_box['height']/2)
                safe_eval(page, f"window.animateClickRipple && window.animateClickRipple({cursor_pos[0]}, {cursor_pos[1]})")
                time.sleep(0.15)
            page.set_input_files("#id_document_file", fixture_path)
            time.sleep(0.6)

        # Start Extraction Pipeline
        cursor_pos = click_element(page, "button:has-text('Start Extraction Pipeline')", cursor_pos, delay_after=1.0)
        page.wait_for_load_state("networkidle")

        # -----------------------------------------------------------------
        # SCENE 4: Split-Screen Human Review Workspace & AI Calculations
        # -----------------------------------------------------------------
        print("  ▶ Scene 4: Split-Screen Review Workspace, Line Items & Calculations")
        time.sleep(0.8)

        # Inspect Document Preview pane on left
        doc_loc = page.locator(".document-pane").first
        doc_loc.wait_for(state="visible", timeout=8000)
        doc_box = doc_loc.bounding_box()
        if doc_box:
            smooth_move(page, cursor_pos[0], cursor_pos[1], doc_box['x'] + 180, doc_box['y'] + 180, steps=12, duration=0.25)
            cursor_pos = (doc_box['x'] + 180, doc_box['y'] + 180)
            time.sleep(0.5)

        # Scroll editor pane to line items
        safe_eval(page, "document.querySelector('.editor-pane').scrollTop = 320")
        time.sleep(0.5)

        # Demonstrate dynamic line items - Click '+ Add Line'
        cursor_pos = click_element(page, "#add-line-btn", cursor_pos, delay_after=0.4)

        # Type in new line description and watch AI account coding trigger
        last_desc_input = ".line-row:last-child .line-desc-input"
        cursor_pos = type_text(page, last_desc_input, "Additional Cloud Compute Reserve Instance", cursor_pos, typing_speed=0.02)
        time.sleep(0.5)

        # Type unit price
        last_price_input = ".line-row:last-child .line-price-input"
        cursor_pos = type_text(page, last_price_input, "350.00", cursor_pos, typing_speed=0.02)
        time.sleep(0.4)

        # Remove the added line with smooth GSAP exit animation
        cursor_pos = click_element(page, ".line-row:last-child .remove-line-btn", cursor_pos, delay_after=0.5)

        # Resolve issue if any present
        if page.locator("form button:has-text('Resolve Issue')").count() > 0:
            cursor_pos = click_element(page, "form button:has-text('Resolve Issue')", cursor_pos, delay_after=0.6)
            page.wait_for_load_state("networkidle")
            time.sleep(0.4)

        # Open Audit Modal to inspect history
        cursor_pos = click_element(page, "button:has-text('Audit History')", cursor_pos, delay_after=0.8)
        cursor_pos = click_element(page, "#audit-modal button[data-modal-close]", cursor_pos, delay_after=0.5)

        # Approve Invoice
        safe_eval(page, "document.getElementById('approve-modal').classList.add('active')")
        time.sleep(0.4)
        cursor_pos = click_element(page, "#approve-modal button:has-text('Confirm & Approve')", cursor_pos, delay_after=1.0)
        page.wait_for_load_state("networkidle")
        time.sleep(0.6)

        # -----------------------------------------------------------------
        # SCENE 5: Accounting Draft Bill Export
        # -----------------------------------------------------------------
        print("  ▶ Scene 5: Exporting Approved Invoice to Accounting Ledger")
        safe_eval(page, "document.querySelector('.editor-pane').scrollTop = 1000")
        time.sleep(0.3)
        
        safe_eval(page, "document.getElementById('export-modal').classList.add('active')")
        time.sleep(0.4)
        cursor_pos = click_element(page, "#export-modal button:has-text('Create Draft Bill Now')", cursor_pos, delay_after=1.0)
        page.wait_for_load_state("networkidle")
        time.sleep(0.6)

        # -----------------------------------------------------------------
        # SCENE 6: Synchronized Accounting Ledger
        # -----------------------------------------------------------------
        print("  ▶ Scene 6: Inspecting Accounting Ledger & JSON Payload")
        page.goto(f"{BASE_URL}/accounting/ledger/")
        page.wait_for_load_state("networkidle")
        time.sleep(0.8)

        # Open JSON Payload Modal
        if page.locator("button:has-text('View JSON')").count() > 0:
            cursor_pos = click_element(page, "button:has-text('View JSON')", cursor_pos, delay_after=0.8)
            cursor_pos = click_element(page, ".modal-overlay.active button[data-modal-close]", cursor_pos, delay_after=0.5)

        # -----------------------------------------------------------------
        # SCENE 7: Exception Queue Triage
        # -----------------------------------------------------------------
        print("  ▶ Scene 7: Exception Queue Filters & Math Mismatch Inspection")
        page.goto(f"{BASE_URL}/exceptions/")
        page.wait_for_load_state("networkidle")
        time.sleep(0.8)

        # Click Math Mismatches filter tab
        cursor_pos = click_element(page, "a:has-text('Math Mismatches')", cursor_pos, delay_after=0.6)
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)

        # Click Duplicate Invoices filter tab
        cursor_pos = click_element(page, "a:has-text('Duplicates')", cursor_pos, delay_after=0.6)
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)

        # -----------------------------------------------------------------
        # SCENE 8: Background Processing Jobs Monitor
        # -----------------------------------------------------------------
        print("  ▶ Scene 8: Background Processing Jobs Monitor")
        page.goto(f"{BASE_URL}/jobs/")
        page.wait_for_load_state("networkidle")
        time.sleep(0.8)

        # -----------------------------------------------------------------
        # SCENE 9: Invoices Repository & Final Return to Dashboard
        # -----------------------------------------------------------------
        print("  ▶ Scene 9: Invoices Repository & Final Return to Dashboard")
        page.goto(f"{BASE_URL}/documents/")
        page.wait_for_load_state("networkidle")
        time.sleep(0.8)

        # Return to Dashboard
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        time.sleep(1.5)

        context.close()
        browser.close()

    print("✅ Raw video recording complete. Processing with FFmpeg...")


def transcode_video():
    """Finds raw webm recorded by Playwright and transcodes to 720p 30fps H.264 MP4."""
    raw_files = list(RAW_VIDEO_DIR.glob("*.webm")) + list(RAW_VIDEO_DIR.glob("*.mp4"))
    if not raw_files:
        raise RuntimeError("No raw video files found in recording directory.")

    raw_file = sorted(raw_files, key=lambda f: f.stat().st_mtime, reverse=True)[0]
    print(f"📦 Transcoding {raw_file.name} -> {FINAL_VIDEO_PATH.name}...")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_file),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(FINAL_VIDEO_PATH)
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FFmpeg error: {res.stderr}")
        raise RuntimeError(f"FFmpeg transcode failed: {res.stderr}")

    file_size_mb = FINAL_VIDEO_PATH.stat().st_size / (1024 * 1024)
    print(f"🎉 Final video created successfully: {FINAL_VIDEO_PATH} ({file_size_mb:.2f} MB)")


if __name__ == "__main__":
    run_recording()
    transcode_video()
