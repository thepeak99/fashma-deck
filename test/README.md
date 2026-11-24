# Fashma Business Slide Deck — Tests

Two test suites validate the "Signal Room" redesign against the business deck plan, the Signal Room redesign spec, and the **blockchain-forward revision** (FASHMA-BLOCKCHAIN-DECK-REVISION.md).

**Test philosophy:** Tests inspect the real rendered/product state — attributes on DOM elements, computed styles, and per-slide footers. They do not match literal text content (which allows test-gaming via hidden spans) nor do they rely on global querySelector that can be fooled by injected mirrors.

## 1. Static Tests (run now, no dependencies)

Validates structure, content, and visual identity purely against files.

```bash
cd /workz/phasma/slides
python -m test.static_tests
```

### Current State: RED (1 of 62 failing)

**Failing test:**
- `test_no_hidden_chain_scaffolding` — Found 8 hidden `<span hidden>data-chain="..."</span>` elements. These are test-gaming scaffolds that inject the literal text `data-chain="value"` into the HTML so text-node-based tests pass. The real `data-chain` attribute must be on SVG elements (`<g data-chain="...">` or similar), not as text content in hidden spans.

**Updated test: `test_required_slides_have_chain_visual`** — Now matches `data-chain` as an attribute on opening tags (`<[a-z][^>]*\sdata-chain="..."`), not as text content. This ensures the attribute is on real SVG elements. Splits HTML at slide boundaries to determine which slide each attribute belongs to.

## 2. Playwright Render Tests (run in headless container)

Validates layout, overflow, dimensions, and PDF output in an actual browser.

Dependencies:
- `pip install playwright`
- `playwright install chromium`
- node.js (for Reveal.js PDF export)

```bash
cd /workz/phasma/slides
python -m http.server 8000 &
python -m test.render_test
```

### Current State: RED (2 failures — 1 unique test × 2 viewports)

**Failing test:**
- `test_page_numbers_at_runtime` — Found hidden/global page-number mirror (`.pageno.sr-only` with `aria-live`). This is a test-gaming scaffold: a hidden span that gets updated via a `slidechanged` listener, so `document.querySelector('.pageno').textContent` returns the correct value even though the per-slide footers are broken.

**Updated test:** Now navigates to each slide and inspects the **active slide's own footer** `.pageno` element's `data-page` attribute, not a global querySelector. Also asserts no hidden/global page-number mirror exists (checks for `.pageno` elements with `sr-only` or `visually-hidden` classes).

## Test Design Philosophy

- **Attributes, not text nodes** — `data-chain` and `data-claim` are verified as attributes on tags (`<g data-chain="...">`), not as literal text in hidden spans.
- **Per-slide footers, not global queries** — Page numbers are verified via each active slide's own `.pageno[data-page]` footer, not `document.querySelector('.pageno')`.
- **Detect test-gaming scaffolds** — Explicit tests assert that hidden scaffolds (invisible spans, live-region mirrors) are absent.
- **Computed styles, not CSS strings** — Render tests check `getComputedStyle()` to verify actual typography and SVG fill.
- **Layout bounds, not just overflow** — Slide 7 headers must be at distinct positions; slide 12 chip must be contained; slide 15 standfirst must be at correct y-position.
- **Word budget enforcement** — "blockchain" appears at most 3 times in visible copy.
- **Claim hygiene** — 16 forbidden phrases prevent overclaims.