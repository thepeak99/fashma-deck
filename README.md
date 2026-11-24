# Fashma Business Slide Deck

A 15-slide business presentation targeting Luxembourg government and business stakeholders. Built with Reveal.js, fully vendored for offline use. Redesigned 2026-11-24 under the "Signal Room" art direction with bespoke SVG instruments, custom chrome, and a true 1600×900 canvas.

## Present the Deck

### Local Server (Recommended)

```bash
cd /workz/phasma/slides
python3 -m http.server 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

### Direct File Open

You can also open `index.html` directly in a browser, though some features (hash navigation) work better with a server.

## Keyboard Controls

| Key | Action |
|-----|--------|
| → / D | Next slide |
| ← / A | Previous slide |
| Home | First slide |
| End | Last slide |
| F | Toggle fullscreen |
| T | Toggle overview |
| N | Toggle speaker notes view |
| ? | Toggle help |

The deck uses custom chrome: Reveal's default controls, progress bar, and slide numbers are disabled in favor of bespoke logo/act/page-number elements. Present with a clicker or keyboard.

## Speaker Notes

Each slide includes speaker notes. To view them:

- Press **N** during the presentation to toggle the notes overlay
- Or open `vendor/reveal/plugin/notes/speaker-view.html` (requires notes plugin enabled)

## PDF Export

To export the deck to PDF:

1. Open the deck with `?pdf-export&print-pdf` appended to the URL
2. Use your browser's print dialog and select "Save as PDF"

Example: [http://localhost:8000/?pdf-export&print-pdf](http://localhost:8000/?pdf-export&print-pdf)

**When printing manually, enable "Background graphics" in the print dialog** — dark backgrounds are part of the design, not an incidental artifact. Without this option the slides will print on white.

The deck is configured for 16:9 widescreen format. The final 15-page PDF produced by verification is at `artifacts/fashma-business-deck.pdf` — the corrected dark 15-page 16:9 export. Slide screenshots and a contact sheet are in `artifacts/`.

The render test (`python3 -m test.render_test`) now includes a raster check that samples representative pages (1, 5, 8, 15) and verifies they are visually dark, guarding against a recurrence of the white-PDF regression.

**Print-mode selector rule:** in `?print-pdf` mode Reveal wraps every slide in a `.pdf-page` div, so child selectors like `.reveal .slides > section.slide` silently stop matching in the PDF. Theme rules that must hold in print (type reset, `text-align: left`, atmosphere layers) use the descendant form `.reveal .slides section.slide`. Gradient text (`background-clip: text`) and CSS `url(#gradient)` fills are swapped for solid ink inside `@media print`, because Chrome's print path outlines or drops them.

## Run Tests

Static tests (62 tests, no dependencies):

```bash
cd /workz/phasma/slides
python3 -m test.static_tests -v
```

Render tests (requires Playwright; produces artifacts including PDF and contact sheet):

```bash
cd /workz/phasma/slides
python3 -m http.server 8000 &
python3 -m test.render_test
```

Render tests verify: slide visibility, overflow at 1600×900 and 1280×720, console errors, network requests, and PDF export. The final 15-page 16:9 PDF is at `artifacts/fashma-business-deck.pdf`.

## Files

- `index.html` — Main slide deck
- `theme/fashma.css` — Fashma dark theme
- `assets/` — Local assets (fonts, logo, constellation SVG)
- `vendor/reveal/` — Vendored Reveal.js and plugins
- `test/` — Test suites

## Design System

- **Background:** Midnight #0a1128
- **Text:** Light #f8f9fa
- **Accent:** Purple #6c63ff
- **Success:** Green #91e1ae
- **Heading font:** Outfit 600-700
- **Body font:** Inter 400-500
- **Card radius:** 15px
- **Visual motif:** Soft iris glow, faint star grain, and vignette on every slide (CSS pseudo-elements, under all content)
- **Polish layer:** the block at the end of `theme/fashma.css` (before print rules) holds the 2026-11-24 polish pass — atmosphere, glassy plates, larger diagram labels, glow on live/mint signals. Same art direction and copy; it only refines rendering.

## Third-Party Licenses

- **Reveal.js** — MIT License (see `vendor/reveal/LICENSE.txt`)
- **Outfit Font** — OFL License (from Google Fonts)
- **Inter Font** — OFL License (from Google Fonts)
