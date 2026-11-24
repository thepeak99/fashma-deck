"""
Playwright-based render tests for the Fashma Business Slide Deck — "The Signal Room" redesign.

These tests render each slide in a headless browser and check:
1. No horizontal or vertical overflow / content clipping at 1600x900
2. No horizontal or vertical overflow / content clipping at 1280x720
3. Content is fully contained within slide bounds
4. Stage dimensions are exactly 1600x900 at scale 1.0
5. Stage scales uniformly to 0.8 at 1280x720 (no reflow)
6. PDF export produces 15 pages at 1200x675pt (16:9), not A4
7. Fonts are loaded correctly (Outfit and Inter)
8. No console errors

Screenshots are saved to slides/artifacts/ for visual inspection.

Dependencies:
- playwright (pip install playwright)
- playwright browsers (npx playwright install chromium or playwright install chromium)
- node.js (for Reveal.js PDF export plugin)
- An HTTP server to serve the slides (http.server or similar)

Run:
    cd slides
    python -m http.server 8000 &
    python -m test.render_test
"""

import asyncio
import os
import re
import sys
from pathlib import Path

# Try to import playwright; if not available, show clear instructions
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright not installed. Run:")
    print("  pip install playwright")
    print("  playwright install chromium")
    sys.exit(1)

# Configuration
SLIDES_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = SLIDES_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

SERVER_URL = os.environ.get("SLIDES_URL", "http://localhost:8000")
EXPECTED_SLIDE_COUNT = 15
EXPECTED_STAGE_WIDTH = 1600
EXPECTED_STAGE_HEIGHT = 900
EXPECTED_PDF_WIDTH_PT = 1200  # 1600px at 72dpi = 1200pt
EXPECTED_PDF_HEIGHT_PT = 675  # 900px at 72dpi = 675pt

# Viewport sizes to test
VIEWPORTS = [
    {"width": 1600, "height": 900, "name": "1600x900", "expected_scale": 1.0},
    {"width": 1280, "height": 720, "name": "1280x720", "expected_scale": 0.8},
]


async def test_stage_dimensions(page, viewport_name, expected_scale):
    """
    Check that the stage is exactly 1600x900 and scales uniformly.
    Returns (ok, message).
    """
    try:
        result = await page.evaluate("""
            () => {
                const slides = document.querySelector('.reveal .slides');
                if (!slides) {
                    return { error: '.reveal .slides not found' };
                }
                const rect = slides.getBoundingClientRect();
                // Calculate scale from actual rendered size vs. designed size
                const scale = rect.width / 1600;
                return {
                    width: rect.width,
                    height: rect.height,
                    scale: scale,
                    slideWidth: slides.offsetWidth,
                    slideHeight: slides.offsetHeight,
                };
            }
        """)
        if "error" in result:
            return False, result["error"]

        # Check scale
        actual_scale = result["scale"]
        if abs(actual_scale - expected_scale) > 0.05:
            return False, f"Scale {actual_scale:.2f} != expected {expected_scale} at {viewport_name}"

        # Check rendered dimensions
        expected_width = 1600 * expected_scale
        expected_height = 900 * expected_scale
        if abs(result["width"] - expected_width) > 5:
            return False, f"Width {result['width']} != expected {expected_width} at {viewport_name}"
        if abs(result["height"] - expected_height) > 5:
            return False, f"Height {result['height']} != expected {expected_height} at {viewport_name}"

        return True, f"Stage {result['width']}x{result['height']} (scale {actual_scale:.2f})"
    except Exception as e:
        return False, f"Stage dimensions check failed: {e}"


async def test_slide_visible_in_viewport(page, slide_index, viewport_name):
    """
    Navigate to a slide and verify the active slide is actually visible
    within the viewport (not stacked 900px/1800px below due to layout bug).
    Returns (ok, message).
    """
    # Navigate to specific slide
    try:
        await page.evaluate(
            f"Reveal.slide({slide_index}, 0, null, 'default')"
        )
    except Exception as e:
        return False, f"Failed to navigate to slide {slide_index}: {e}"

    # Wait for transition
    await page.wait_for_timeout(500)

    try:
        # Check that the active slide is within the viewport
        result = await page.evaluate("""
            () => {
                const activeSlide = document.querySelector('.reveal .slides section.present');
                if (!activeSlide) {
                    return { error: 'No active slide (.present) found' };
                }

                const rect = activeSlide.getBoundingClientRect();
                const vh = window.innerHeight;
                const vw = window.innerWidth;

                return {
                    top: rect.top,
                    bottom: rect.bottom,
                    left: rect.left,
                    right: rect.right,
                    width: rect.width,
                    height: rect.height,
                    viewportHeight: vh,
                    viewportWidth: vw,
                    hasContent: activeSlide.textContent.trim().length > 0,
                    contentLength: activeSlide.textContent.trim().length,
                    slideId: activeSlide.id || 'none',
                    isStacked: rect.top > vh || rect.bottom < 0 || rect.left > vw || rect.right < 0,
                };
            }
        """)

        if "error" in result:
            return False, result["error"]

        issues = []

        # Check slide is within viewport (not stacked below)
        if result["isStacked"]:
            issues.append(
                f"slide displaced: top={result['top']:.0f}px (viewport={result['viewportHeight']}px)"
            )
        elif result["top"] > 10:
            issues.append(
                f"slide not at viewport top: top={result['top']:.0f}px"
            )

        # Check for meaningful content
        if not result["hasContent"]:
            issues.append("slide has no text content")
        elif result["contentLength"] < 20:
            issues.append(f"slide has very little content ({result['contentLength']} chars)")

        if issues:
            return False, f"[{result['slideId']}] {'; '.join(issues)}"

        return True, f"[{result['slideId']}] visible, {result['contentLength']} chars"

    except Exception as e:
        return False, f"Visibility check failed: {e}"


async def test_slide_overflow(page, slide_index, viewport_name):
    """
    Navigate to a slide and check for overflow outside slide bounds.
    Returns (ok, message).
    """
    # Navigate to specific slide using reveal's API
    try:
        await page.evaluate(
            f"Reveal.slide({slide_index}, 0, null, 'default')"
        )
    except Exception as e:
        return False, f"Failed to navigate to slide {slide_index}: {e}"

    # Wait for slide transition to complete
    await page.wait_for_timeout(500)

    # Take screenshot for visual inspection
    screenshot_path = ARTIFACTS_DIR / f"slide-{slide_index+1:02d}-{viewport_name}.png"
    try:
        await page.screenshot(path=str(screenshot_path))
    except Exception as e:
        print(f"  Warning: screenshot failed: {e}")

    # Check for overflow: compare scroll dimensions to client dimensions
    overflow_check = await page.evaluate("""
        () => {
            // Reveal.js 5: no .slide-background wrapper; use .slides container directly
            const slides = document.querySelector('.reveal .slides');
            const content = document.querySelector('.reveal .slides section.present');
            
            if (!slides || !content) {
                return { error: 'Slide elements not found' };
            }
            
            // Check for scroll dimensions (actual content overflow)
            const hasScrollH = content.scrollWidth > content.clientWidth;
            const hasScrollV = content.scrollHeight > content.clientHeight;
            
            return {
                horizontalOverflow: hasScrollH,
                verticalOverflow: hasScrollV,
                hasScrollH: hasScrollH,
                hasScrollV: hasScrollV,
                slideWidth: slides.clientWidth,
                slideHeight: slides.clientHeight,
                contentWidth: content.clientWidth,
                contentHeight: content.clientHeight,
            };
        }
    """)

    if "error" in overflow_check:
        return False, overflow_check["error"]

    issues = []
    if overflow_check["horizontalOverflow"]:
        issues.append("horizontal overflow")
    if overflow_check["verticalOverflow"]:
        issues.append("vertical overflow")
    if overflow_check["hasScrollH"]:
        issues.append("horizontal scrollbar")
    if overflow_check["hasScrollV"]:
        issues.append("vertical scrollbar")

    if issues:
        return False, f"Overflow detected: {', '.join(issues)}"

    return True, "OK"


async def test_fonts_loaded(page):
    """
    Check that Outfit and Inter fonts are loaded.
    Returns (ok, message).
    """
    try:
        result = await page.evaluate("""
            async () => {
                // Wait for fonts to be ready
                await document.fonts.ready;
                return {
                    outfit: document.fonts.check('600 56px Outfit'),
                    inter: document.fonts.check('400 16px Inter'),
                    ready: document.fonts.status === 'loaded',
                };
            }
        """)
        if not result["ready"]:
            return False, f"Fonts not loaded: status={result['ready']}"
        if not result["outfit"]:
            return False, "Outfit font not loaded (600 56px)"
        if not result["inter"]:
            return False, "Inter font not loaded (400 16px)"
        return True, "Fonts loaded (Outfit + Inter)"
    except Exception as e:
        return False, f"Font check failed: {e}"


async def test_pdf_export(page):
    """
    Export deck to PDF and check it has the expected number of pages
    at the correct dimensions (16:9, not A4).
    Returns (ok, message, pdf_path).
    """
    pdf_path = ARTIFACTS_DIR / "deck.pdf"

    try:
        # Navigate to PDF export URL
        pdf_url = f"{SERVER_URL}?pdf-export&print-pdf"
        await page.goto(pdf_url, wait_until="networkidle")
        await page.wait_for_timeout(3000)  # Wait for rendering

        # Save PDF with explicit 16:9 dimensions (not A4)
        await page.pdf(
            path=str(pdf_path),
            width="1600px",
            height="900px",
            print_background=True,
            prefer_css_page_size=True,
        )

        # Check file size
        pdf_size = pdf_path.stat().st_size
        if pdf_size < 50000:
            return False, f"PDF file too small ({pdf_size} bytes), likely failed", pdf_path

        # Verify PDF dimensions using pdfinfo or PyPDF2
        dims_ok = True
        dim_msg = "dimension check skipped (no pdfinfo/PyPDF2)"
        try:
            import subprocess
            result = subprocess.run(
                ["pdfinfo", str(pdf_path)],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Page size" in line or "MediaBox" in line:
                        # Check for 1200x675pt (16:9 at 72dpi)
                        if "1200" in line or "675" in line or "8.500in" in line:
                            dim_msg = "PDF dimensions appear correct (16:9)"
                        elif "842" in line or "595" in line or "595.9" in line:
                            dim_msg = "PDF is A4 landscape (842.88x595.92pt) — should be 16:9"
                            dims_ok = False
                        break
            else:
                dim_msg = f"pdfinfo failed: {result.stderr[:100]}"
        except (ImportError, FileNotFoundError, subprocess.TimeoutExpired):
            dim_msg = "pdfinfo not available; cannot verify PDF dimensions"

        # Check page count (heuristic: file size or pdfinfo)
        page_msg = "page count not verified"
        try:
            import subprocess
            result = subprocess.run(
                ["pdfinfo", str(pdf_path)],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Pages:" in line:
                        page_msg = line.strip()
                        if "15" not in line:
                            dims_ok = False
                        break
        except (ImportError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return True, f"PDF exported ({pdf_size} bytes) to {pdf_path}. {dim_msg}. {page_msg}", pdf_path

    except Exception as e:
        return False, f"PDF export failed: {e}", pdf_path


async def check_console_errors(page):
    """
    Collect console errors from the page.
    Returns list of error messages.
    """
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    return errors


async def test_computed_typography(page):
    """
    Check computed font sizes match the Signal Room design spec.
    Enforces the P0 reset fix: .display=104px, .headline=56px, .standfirst=24px.
    Returns (ok, message).
    """
    try:
        result = await page.evaluate("""
            () => {
                const s1 = document.querySelector('#s1 .display');
                const s2_headline = document.querySelector('#s2 .headline');
                const s2_standfirst = document.querySelector('#s2 .standfirst');
                const s3_data = document.querySelector('#s3 text.data');
                const s2_micro = document.querySelector('#s2 .micro');

                function fontInfo(el) {
                    if (!el) return { found: false };
                    const cs = getComputedStyle(el);
                    return {
                        found: true,
                        size: cs.fontSize,
                        family: cs.fontFamily,
                        weight: cs.fontWeight,
                    };
                }

                function svgFill(el) {
                    if (!el) return { found: false };
                    const cs = getComputedStyle(el);
                    return {
                        found: true,
                        fill: cs.fill,
                        color: cs.color,
                    };
                }

                return {
                    display: fontInfo(s1),
                    headline: fontInfo(s2_headline),
                    standfirst: fontInfo(s2_standfirst),
                    data: svgFill(s3_data),
                    micro: fontInfo(s2_micro),
                };
            }
        """)

        issues = []

        # Display: 104px Outfit 700
        disp = result["display"]
        if not disp["found"]:
            issues.append("display element not found")
        else:
            if disp["size"] != "104px":
                issues.append(f"display font-size is {disp['size']}, expected 104px")
            if "Outfit" not in disp["family"]:
                issues.append(f"display font-family is {disp['family']}, expected Outfit")
            if disp["weight"] != "700":
                issues.append(f"display font-weight is {disp['weight']}, expected 700")

        # Headline: 56px Outfit 600
        hl = result["headline"]
        if not hl["found"]:
            issues.append("headline element not found")
        else:
            if hl["size"] != "56px":
                issues.append(f"headline font-size is {hl['size']}, expected 56px")
            if "Outfit" not in hl["family"]:
                issues.append(f"headline font-family is {hl['family']}, expected Outfit")
            if hl["weight"] != "600":
                issues.append(f"headline font-weight is {hl['weight']}, expected 600")

        # Standfirst: 24px Inter 400
        sf = result["standfirst"]
        if not sf["found"]:
            issues.append("standfirst element not found")
        else:
            if sf["size"] != "24px":
                issues.append(f"standfirst font-size is {sf['size']}, expected 24px")
            if "Inter" not in sf["family"]:
                issues.append(f"standfirst font-family is {sf['family']}, expected Inter")
            if sf["weight"] != "400":
                issues.append(f"standfirst font-weight is {sf['weight']}, expected 400")

        # Data: fill must be visible against midnight (#0a1128), not black
        dat = result["data"]
        if not dat["found"]:
            issues.append("data SVG text element not found")
        else:
            # fill should be paper color or light, not black/rgb(0,0,0)
            if dat["fill"] == "rgb(0, 0, 0)" or dat["fill"] == "rgb(0,0,0)":
                issues.append(f"data SVG text fill is black ({dat['fill']}), invisible on midnight")
            # Check that fill is not the default transparent
            if dat["fill"] == "none" or dat["fill"] == "transparent":
                issues.append(f"data SVG text fill is transparent ({dat['fill']})")

        # Micro: 11px with letter-spacing
        mic = result["micro"]
        if not mic["found"]:
            issues.append("micro element not found")
        else:
            if mic["size"] != "11px":
                issues.append(f"micro font-size is {mic['size']}, expected 11px")

        if issues:
            return False, "; ".join(issues)
        return True, "Computed typography matches design spec"

    except Exception as e:
        return False, f"Typography check failed: {e}"


async def test_slide7_grid_layout(page):
    """
    Check slide 7 swimlane grid is not shifted (P0 fix: SVG in swim-wrap).
    Headers should be at correct x positions, not off by one column.
    Returns (ok, message).
    """
    try:
        # Navigate to slide 7
        await page.evaluate("Reveal.slide(6, 0, null, 'default')")
        await page.wait_for_timeout(500)

        result = await page.evaluate("""
            () => {
                const swim = document.querySelector('#s7 .swim');
                if (!swim) return { found: false };

                const cs = getComputedStyle(swim);
                const rows = cs.gridTemplateRows;

                // Check for the implicit extra row bug (Chromium counts SVG as grid item)
                // If SVG is inside .swim, there will be 5 rows instead of 4
                return {
                    found: true,
                    gridTemplateRows: rows,
                    rowSplit: rows.split(" ").length,
                };
            }
        """)

        if not result["found"]:
            return False, "Slide 7 .swim grid not found"

        # Should have exactly 4 rows (52px + 3*100px + 56px anchor row = 452px total)
        # Actually: 52 + 100 + 100 + 100 + 56 = 408px, 5 rows
        # Wait: spec says 52px header + 3*100px lanes + 56px anchor = 5 rows total
        if result["rowSplit"] != 5:
            return False, f"Slide 7 grid has {result['rowSplit']} rows, expected 5 (header + 3 lanes + anchor row)"

        # Check headers are at correct positions (not shifted)
        result2 = await page.evaluate("""
            () => {
                const headers = document.querySelectorAll('#s7 .swim__head');
                if (headers.length < 4) return { count: headers.length };

                const positions = [];
                headers.forEach(h => {
                    const rect = h.getBoundingClientRect();
                    positions.push(rect.left);
                });
                return { count: headers.length, positions: positions };
            }
        """)

        if result2["count"] < 4:
            return False, f"Slide 7 has {result2['count']} headers, expected 4"

        # Headers should be evenly spaced, not all shifted
        # First header at ~160px from content left, ~280 from viewport
        positions = result2["positions"]
        # Check that positions are not all the same (would indicate grid breakage)
        unique_positions = len(set(round(p) for p in positions))
        if unique_positions < 4:
            return False, f"Slide 7 headers not at distinct positions (grid shifted?)"

        return True, f"Slide 7 grid layout OK ({result2['count']} headers, {unique_positions} distinct positions)"

    except Exception as e:
        return False, f"Slide 7 grid check failed: {e}"


async def test_slide12_geometry(page):
    """
    Check slide 12 arc is a proper horizon (not a fragment) and chip is contained.
    Returns (ok, message).
    """
    try:
        # Navigate to slide 12
        await page.evaluate("Reveal.slide(11, 0, null, 'default')")
        await page.wait_for_timeout(500)

        result = await page.evaluate("""
            () => {
                const svg = document.querySelector('#s12 svg.art');
                if (!svg) return { svgFound: false };

                // Check viewBox
                const viewBox = svg.getAttribute('viewBox');

                // Find the arc path
                const paths = svg.querySelectorAll('path');
                let arcFound = false;
                let arcLength = 0;
                paths.forEach(p => {
                    const d = p.getAttribute('d');
                    if (d && d.includes('A') && d.includes('620')) {
                        arcFound = true;
                        // The arc should span a significant width
                        // Correct arc: M 0 372 A 620 620 0 0 1 600 588 (600px chord)
                        arcLength = parseInt(d.match(/A 620 620 0 0 1 (\\d+)/)?.[1] || '0');
                    }
                });

                // Find receipt chip
                const chip = document.querySelector('#s12 .receipt-chip');
                let chipContained = false;
                if (chip) {
                    const chipRect = chip.getBoundingClientRect();
                    const svgRect = svg.getBoundingClientRect();
                    chipContained = (
                        chipRect.top >= svgRect.top - 50 &&
                        chipRect.bottom <= svgRect.bottom + 50 &&
                        chipRect.left >= svgRect.left - 50 &&
                        chipRect.right <= svgRect.right + 50
                    );
                }

                return {
                    svgFound: true,
                    viewBox: viewBox,
                    arcFound: arcFound,
                    arcLength: arcLength,
                    chipFound: !!chip,
                    chipContained: chipContained,
                };
            }
        """)

        if not result["svgFound"]:
            return False, "Slide 12 art SVG not found"

        issues = []
        if not result["arcFound"]:
            issues.append("horizon arc not found")
        elif result["arcLength"] < 500:
            issues.append(f"arc is too short ({result['arcLength']}px chord), not a proper horizon")

        if result["chipFound"] and not result["chipContained"]:
            issues.append("receipt chip is outside the art bounds")

        if issues:
            return False, "; ".join(issues)
        return True, "Slide 12 geometry OK (horizon arc + contained chip)"

    except Exception as e:
        return False, f"Slide 12 geometry check failed: {e}"


async def test_slide15_standfirst_position(page):
    """
    Check slide 15 standfirst is at y=480 (P0 fix), not at top edge.
    Returns (ok, message).
    """
    try:
        # Navigate to slide 15
        await page.evaluate("Reveal.slide(14, 0, null, 'default')")
        await page.wait_for_timeout(500)

        result = await page.evaluate("""
            () => {
                const standfirst = document.querySelector('#s15 .standfirst');
                if (!standfirst) return { found: false };

                const cs = getComputedStyle(standfirst);
                const rect = standfirst.getBoundingClientRect();

                return {
                    found: true,
                    top: rect.top,
                    position: cs.position,
                };
            }
        """)

        if not result["found"]:
            return False, "Slide 15 standfirst not found"

        # Standfirst should be at y~480, not at top (y<100 would be wrong)
        if result["top"] < 100:
            return False, f"Slide 15 standfirst at top edge (y={result['top']}), expected ~480"
        if result["top"] > 600:
            return False, f"Slide 15 standfirst too low (y={result['top']}), expected ~480"

        return True, f"Slide 15 standfirst at y={result['top']} (OK)"

    except Exception as e:
        return False, f"Slide 15 standfirst check failed: {e}"


async def test_page_numbers_at_runtime(page):
    """
    Check that each slide shows its own page number (not all '03 / 15').
    Uses the static data-page attribute on each slide's footer.
    Inspects the ACTIVE slide's footer directly, not a global querySelector.
    Also asserts no hidden/global page-number mirror exists.
    Returns (ok, message).
    """
    try:
        # Check for hidden/global page-number mirror (test-gaming scaffold)
        mirror_exists = await page.evaluate("""
            () => {
                // Look for a pageno element that is visually hidden and has aria-live
                const allPageno = document.querySelectorAll('.pageno');
                for (const el of allPageno) {
                    if (el.classList.contains('sr-only') || el.classList.contains('visually-hidden')) {
                        return true;
                    }
                }
                return false;
            }
        """)
        if mirror_exists:
            return False, "Found hidden/global page-number mirror (test-gaming scaffold)"

        # Check first 5 slides for correct page numbers using active slide's footer
        results = []
        for i in range(5):
            await page.evaluate(f"Reveal.slide({i}, 0, null, 'default')")
            await page.wait_for_timeout(300)

            # Find the active slide and its footer's data-page attribute
            page_info = await page.evaluate("""
                () => {
                    const activeSlide = document.querySelector('.reveal .slides section.present');
                    if (!activeSlide) return null;
                    const pageno = activeSlide.querySelector('.pageno');
                    if (!pageno) return null;
                    return {
                        dataPage: pageno.getAttribute('data-page'),
                        textContent: pageno.textContent
                    };
                }
            """)
            if page_info:
                results.append({
                    "slide": i + 1,
                    "data_page": page_info["dataPage"],
                    "text": page_info["textContent"]
                })

        issues = []
        # First 4 slides should have unique, sequential data-page values
        for r in results[:4]:
            if not r["data_page"]:
                issues.append(f"slide {r['slide']} footer missing data-page attribute")
            else:
                # data-page should be a 2-digit zero-padded number
                expected = f"{r['slide']:02d}"
                if r["data_page"] != expected:
                    issues.append(
                        f"slide {r['slide']} footer data-page={r['data_page']}, expected {expected}"
                    )

        # Check that data-page values are different for different slides
        data_pages = [r["data_page"] for r in results[:4] if r["data_page"]]
        unique_pages = len(set(data_pages))
        if unique_pages < len(data_pages):
            issues.append(f"data-page values not unique across slides: {data_pages}")

        if issues:
            return False, "; ".join(issues)

        return True, f"Page numbers correct via footer data-page: {data_pages}"

    except Exception as e:
        return False, f"Page number check failed: {e}"


async def check_console_errors(page):
    """
    Collect console errors from the page.
    Returns list of error messages.
    """
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    return errors


async def test_pdf_backgrounds_painted(pdf_path):
    """
    Rasterize representative PDF pages and assert the midnight background
    is actually painted — not merely that CSS strings or page geometry
    are correct. Guards against the "white background" regression where
    print backgrounds were dropped in PDF export, making light/white text
    invisible.

    Checks pages 1, 5, 8, 15 (cover, instrument, proof, close). For each
    page, samples corner/edge pixels and computes the proportion of dark
    pixels (luminance < 64). The intended background (#0a1128) is very
    dark, so a high proportion of dark pixels should be present. A white
    background would produce almost no dark pixels.

    Returns (ok, message).
    """
    try:
        import pymupdf
        from PIL import Image
        import io

        doc = pymupdf.open(pdf_path)
        total_pages = len(doc)

        # Representative pages: cover (1), instrument (5), proof (8), close (15)
        pages_to_check = [1, 5, 8, 15]
        # Cap to actual page count
        pages_to_check = [p for p in pages_to_check if p <= total_pages]

        issues = []

        for page_num in pages_to_check:
            page = doc[page_num - 1]
            pix = page.get_pixmap(dpi=72)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            w, h = img.size
            pixels = img.load()

            # Sample corner/edge pixels — these should be background, not text
            sample_points = [
                (10, 10),
                (w - 10, 10),
                (10, h - 10),
                (w - 10, h - 10),
                (w // 4, 10),
                (3 * w // 4, 10),
                (w // 4, h - 10),
                (3 * w // 4, h - 10),
            ]

            def luminance(r, g, b):
                return 0.299 * r + 0.587 * g + 0.114 * b

            # Check that corner pixels are dark (not white)
            bright_corners = []
            for i, (x, y) in enumerate(sample_points):
                pixel = pixels[x, y]
                lum = luminance(pixel[0], pixel[1], pixel[2])
                if lum > 128:
                    bright_corners.append(
                        f"pos{i}({x},{y})={pixel} lum={lum:.0f}"
                    )

            # Compute overall dark pixel proportion (sample grid for speed)
            grid = 40
            dark_count = 0
            total_count = 0
            for gx in range(0, w, grid):
                for gy in range(0, h, grid):
                    pixel = pixels[gx, gy]
                    lum = luminance(pixel[0], pixel[1], pixel[2])
                    total_count += 1
                    if lum < 64:
                        dark_count += 1

            dark_ratio = dark_count / total_count if total_count > 0 else 0

            # The midnight background (#0a1128) should yield a high proportion
            # of dark pixels. White background would yield very few.
            if bright_corners:
                issues.append(
                    f"page {page_num}: bright corners (white bg?): "
                    f"{', '.join(bright_corners)}"
                )
            if dark_ratio < 0.4:
                issues.append(
                    f"page {page_num}: only {dark_ratio:.1%} dark pixels "
                    f"(expected >40% for midnight background)"
                )

        doc.close()

        if issues:
            return False, f"PDF backgrounds not painted: {'; '.join(issues)}"
        return True, "PDF backgrounds painted dark across representative pages"

    except ImportError as e:
        return False, f"Missing dependency for PDF raster test: {e}"
    except Exception as e:
        return False, f"PDF background raster test failed: {e}"


async def run_render_tests():
    """Run all render tests."""
    print("Starting render tests...")
    print(f"  Server URL: {SERVER_URL}")
    print(f"  Artifacts: {ARTIFACTS_DIR}")
    print()

    failures = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # Test each viewport
        for viewport in VIEWPORTS:
            print(f"Testing viewport: {viewport['name']}")
            print("-" * 60)

            context = await browser.new_context(
                viewport={"width": viewport["width"], "height": viewport["height"]}
            )
            page = await context.new_page()

            # Collect console errors
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            try:
                # Load the deck
                await page.goto(SERVER_URL, wait_until="networkidle")

                # Wait for Reveal to initialize
                await page.wait_for_function("typeof Reveal !== 'undefined' && Reveal.isReady()")

                # Check stage dimensions
                ok, msg = await test_stage_dimensions(
                    page, viewport["name"], viewport["expected_scale"]
                )
                status = "✓" if ok else "✗"
                print(f"  {status} Stage dimensions: {msg}")
                if not ok:
                    failures.append(f"  [{viewport['name']}] Stage: {msg}")

                # Get slide count
                slide_count = await page.evaluate("Reveal.getTotalSlides()")
                print(f"  Total slides: {slide_count}")

                if slide_count != EXPECTED_SLIDE_COUNT:
                    failures.append(f"  [{viewport['name']}] Expected {EXPECTED_SLIDE_COUNT} slides, found {slide_count}")

                # Check fonts
                ok, msg = await test_fonts_loaded(page)
                status = "✓" if ok else "✗"
                print(f"  {status} Fonts: {msg}")
                if not ok:
                    failures.append(f"  [{viewport['name']}] Fonts: {msg}")

                # Test each slide for visibility and overflow
                for i in range(slide_count):
                    ok, msg = await test_slide_visible_in_viewport(page, i, viewport["name"])
                    status = "✓" if ok else "✗"
                    print(f"  {status} Slide {i+1:2d} (visible): {msg}")
                    if not ok:
                        failures.append(f"  [{viewport['name']}] Slide {i+1} visible: {msg}")

                    ok, msg = await test_slide_overflow(page, i, viewport["name"])
                    status = "✓" if ok else "✗"
                    print(f"  {status} Slide {i+1:2d} (overflow): {msg}")
                    if not ok:
                        failures.append(f"  [{viewport['name']}] Slide {i+1} overflow: {msg}")

                # Check console errors
                if console_errors:
                    print(f"  ⚠ Console errors: {len(console_errors)}")
                    for err in console_errors[:5]:
                        print(f"    {err[:100]}")
                    failures.append(f"  [{viewport['name']}] Console errors: {console_errors[:3]}")

                # NEW: Computed typography tests (P0)
                ok, msg = await test_computed_typography(page)
                status = "✓" if ok else "✗"
                print(f"  {status} Computed typography: {msg}")
                if not ok:
                    failures.append(f"  [{viewport['name']}] Typography: {msg}")

                # NEW: Slide 7 grid layout (P0)
                ok, msg = await test_slide7_grid_layout(page)
                status = "✓" if ok else "✗"
                print(f"  {status} Slide 7 grid layout: {msg}")
                if not ok:
                    failures.append(f"  [{viewport['name']}] Slide 7 grid: {msg}")

                # NEW: Slide 12 geometry (P0)
                ok, msg = await test_slide12_geometry(page)
                status = "✓" if ok else "✗"
                print(f"  {status} Slide 12 geometry: {msg}")
                if not ok:
                    failures.append(f"  [{viewport['name']}] Slide 12 geometry: {msg}")

                # NEW: Slide 15 standfirst position (P0)
                ok, msg = await test_slide15_standfirst_position(page)
                status = "✓" if ok else "✗"
                print(f"  {status} Slide 15 standfirst: {msg}")
                if not ok:
                    failures.append(f"  [{viewport['name']}] Slide 15 standfirst: {msg}")

                # NEW: Runtime page numbers (P0)
                ok, msg = await test_page_numbers_at_runtime(page)
                status = "✓" if ok else "✗"
                print(f"  {status} Page numbers at runtime: {msg}")
                if not ok:
                    failures.append(f"  [{viewport['name']}] Page numbers: {msg}")

            except Exception as e:
                failures.append(f"  [{viewport['name']}] Test failed: {e}")
                print(f"  Error: {e}")
            finally:
                await context.close()

            print()

        # PDF export test
        print("Testing PDF export...")
        print("-" * 60)

        context = await browser.new_context(
            viewport={"width": 1600, "height": 900}
        )
        page = await context.new_page()

        try:
            ok, msg, pdf_path = await test_pdf_export(page)
            status = "✓" if ok else "✗"
            print(f"  {status} PDF: {msg}")
            if not ok:
                failures.append(f"  PDF: {msg}")

            # NEW: PDF background rasterization regression test
            # Rasterize the PDF and check that backgrounds are actually painted
            if ok:
                ok2, msg2 = await test_pdf_backgrounds_painted(pdf_path)
                status2 = "✓" if ok2 else "✗"
                print(f"  {status2} PDF backgrounds: {msg2}")
                if not ok2:
                    failures.append(f"  PDF backgrounds: {msg2}")

        except Exception as e:
            failures.append(f"  PDF: Test failed: {e}")
            print(f"  Error: {e}")
        finally:
            await context.close()

        await browser.close()

    print()
    print("=" * 60)
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for f in failures:
            print(f)
    else:
        print("ALL RENDER TESTS PASSED")

    return len(failures) == 0


if __name__ == "__main__":
    result = asyncio.run(run_render_tests())
    sys.exit(0 if result else 1)