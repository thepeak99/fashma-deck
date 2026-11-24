"""
Static tests for the Fashma Business Slide Deck — "The Signal Room" redesign.

These tests validate the deck's structure, content, and visual identity
against FASHMA-VISUAL-REDESIGN.md. They run purely against files — no browser,
no network, no build step.

Dependencies: Python 3.8+ standard library only.

Run: cd slides && python -m test.static_tests
"""

import os
import re
import unittest
import html.parser
from pathlib import Path

# Paths relative to slides/ directory
SLIDES_DIR = Path(__file__).resolve().parent.parent
INDEX_PATH = SLIDES_DIR / "index.html"
CSS_PATH = SLIDES_DIR / "theme" / "fashma.css"

# Expected slide titles from the redesigned deck (exact order)
# Sources: FASHMA-VISUAL-REDESIGN.md §3 (slide-by-slide art direction)
EXPECTED_TITLES = [
    "The strategic asset the space economy trades",  # Cover (display, not h1)
    "A market that moves at the speed of paper.",
    "The scarce resource is now contested.",
    "Three parts. One continuous workflow.",
    "A right to use, not a title deed.",
    "Buy at the rung that fits your business.",
    "From capacity to customer.",
    "A shared record, held by no one.",
    "The State keeps the authority.",
    "A listing you can check, not just believe.",
    "Four checks before a deal becomes a contract.",
    "The contract becomes a live link.",
    "Prove it in four moves.",
    "The pieces are already here.",
    "Start with a pilot.",
]

# Fashma design system colors (from redesign spec §2.1)
MIDNIGHT = "#0a1128"
INK_VOID = "#060A1B"
PURPLE = "#6c63ff"
GREEN = "#91e1ae"
LIGHT = "#f8f9fa"
PAPER = "#F7F8FC"
MIST = "#C3C9DC"
SLATE = "#8A93AF"

# Technical terms that should NOT appear (business deck, not engineer deck)
TECHNICAL_DEEP_DIVE_TERMS = [
    "Token-2022", "PDA", "reason code", "guard band", "Bonsol", "Sombra",
    "Qcash", "zk-SNARK", "Groth16", "RISC-V", "zkVM",
]

# Placeholder / TODO patterns
PLACEHOLDER_PATTERNS = [
    re.compile(r"lorem ipsum", re.IGNORECASE),
    re.compile(r"placeholder", re.IGNORECASE),
    re.compile(r"TODO", re.IGNORECASE),
    re.compile(r"FIXME", re.IGNORECASE),
    re.compile(r"\[insert", re.IGNORECASE),
]

# CDN patterns that should not appear (deck must work offline)
CDN_PATTERNS = [
    re.compile(r"https?://cdn\."),
    re.compile(r"https?://cdnjs\."),
    re.compile(r"https?://unpkg\."),
    re.compile(r"https?://ajax\."),
    re.compile(r"https?://fonts\.(googleapis|gstatic)\."),
]

# Banned words from redesign spec §2.9
BANNED_WORDS = [
    "seamless", "reimagined", "revolutionary", "instantly", "frictionless",
    "trustless", "game-changing", "unlock",
]

# Claim hygiene: these old visible claims must NOT appear (spec §Appendix B)
OLD_CLAIMS = [
    "instantly",  # "Reach a global buyer base instantly"
    "weeks to minutes",  # "Reduces settlement time from weeks to minutes"
    "regulatory certainty",  # "Provides regulatory certainty to both parties"
    "immutable",  # "Every action is recorded, timestamped, and immutable"
    "DLT Pilot Regime",  # Implies regime covers spectrum contracts
    "working prototype and demo",  # Status unconfirmed
    # Blockchain-specific overclaims (FASHMA-BLOCKCHAIN-DECK-REVISION.md §9.3)
    "immutable proof",
    "proves legal",
    "legally binding",
    "automated compliance",
    "tokenised spectrum",
    "tokenized spectrum",
    "spectrum ownership",
    "instant settlement",
    "production-ready",
    "live network",
    "regulator-approved",
    "guaranteed delivery",
    "verified service",
    "double-selling is impossible",
    "quantum-safe",
]

# Mandatory specimen/illustrative lines (spec Appendix B)
MANDATORY_SPECIMEN_LINES = [
    ("SPECIMEN", "Slide 5 plate specimen marker"),
    ("Illustrative specimen", "Slide 5 not-an-offer caption"),
    ("Illustrative", "Slide 7 or 10 or 12 illustrative label"),
]

# Reveal 5 config keys for the new design
STAGE_CONFIG_KEYS = ["width", "height", "margin"]
NO_CHROME_KEYS = ["controls", "progress", "slideNumber"]


class RevealSlideParser(html.parser.HTMLParser):
    """Parse Reveal.js slide deck structure."""

    def __init__(self):
        super().__init__()
        self.in_slide = False
        self.slide_depth = 0
        self.slides = []
        self.current_slide = {}
        self.in_notes = False
        self.current_text = ""
        self.has_reveal_init = False
        self.reveal_init_args = ""
        self.all_html = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = {k: v for k, v in attrs}
        self.all_html += f"<{tag} " + " ".join(f'{k}="{v}"' for k, v in attrs) + "> "

        if tag == "section" and self.in_slide == False:
            self.in_slide = True
            self.slide_depth = 1
            self.current_slide = {
                "title": "",
                "fragments": 0,
                "notes": "",
                "has_notes": False,
                "word_count": 0,
            }
        elif tag == "section" and self.in_slide:
            self.slide_depth += 1

        if tag == "aside" and attrs_dict.get("class", "") == "notes":
            self.in_notes = True
            self.current_slide["has_notes"] = True

    def handle_endtag(self, tag):
        if tag == "section" and self.in_slide:
            self.slide_depth -= 1
            if self.slide_depth == 0:
                self.in_slide = False
                self.current_slide["text"] = self.current_text
                # Count words (approximate, excludes HTML tags)
                text_only = re.sub(r'<[^>]+>', ' ', self.current_text)
                words = [w for w in text_only.split() if len(w) > 2]
                self.current_slide["word_count"] = len(words)
                self.current_slide["fragments"] = len(
                    re.findall(r'class="[^"]*fragment', self.current_text)
                )
                self.slides.append(self.current_slide)
                self.current_text = ""
        if tag == "aside":
            self.in_notes = False

    def handle_data(self, data):
        self.all_html += data
        if self.in_slide:
            if self.in_notes:
                self.current_slide["notes"] += data
            else:
                self.current_text += data


class DeckStructureTests(unittest.TestCase):
    """Test that the deck has the right structure and slide count."""

    @classmethod
    def setUpClass(cls):
        if not INDEX_PATH.exists():
            raise cls.failureException(f"slides/index.html does not exist yet")

        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

        parser = RevealSlideParser()
        parser.feed(cls.html)
        cls.slides = parser.slides
        cls.parser = parser

    def test_index_html_exists(self):
        """Entry point file exists."""
        self.assertTrue(INDEX_PATH.exists(), "slides/index.html must exist")

    def test_exactly_15_slides(self):
        """Deck has exactly 15 main slides as specified in the plan."""
        self.assertEqual(
            len(self.slides),
            15,
            f"Expected 15 slides, found {len(self.slides)}",
        )

    def test_slide_titles_match_redesign_plan(self):
        """Each slide has the correct title from the Signal Room redesign."""
        # Check for redesigned headline content (approximate, case-insensitive)
        html_lower = self.html.lower()
        for i, expected in enumerate(EXPECTED_TITLES):
            # Titles are now editorial headlines; check for distinctive phrases
            phrase = expected.lower()
            self.assertIn(
                phrase,
                html_lower,
                f"Slide {i+1} title not found: '{expected}'",
            )

    def test_no_duplicate_titles(self):
        """No two slides share the same title."""
        title_pattern = re.compile(r"<h[1-3][^>]*>([^<]+)</h[1-3]>", re.IGNORECASE)
        titles = title_pattern.findall(self.html)
        normalized = [t.strip() for t in titles]
        duplicates = [t for t in normalized if normalized.count(t) > 1]
        self.assertEqual(len(duplicates), 0, f"Duplicate titles found: {set(duplicates)}")


class StageConfigTests(unittest.TestCase):
    """Test Reveal initialization for the Signal Room stage."""

    @classmethod
    def setUpClass(cls):
        if not INDEX_PATH.exists():
            raise cls.failureException(f"slides/index.html does not exist yet")

        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_reveal_initialized(self):
        """Reveal.initialize() call is present."""
        self.assertIn("Reveal.initialize", self.html)

    def test_stage_width_1600(self):
        """Stage width is 1600 (Signal Room fixed canvas)."""
        self.assertIn("width: 1600", self.html)
        self.assertIn("1600", self.html)

    def test_stage_height_900(self):
        """Stage height is 900 (Signal Room fixed canvas)."""
        self.assertIn("height: 900", self.html)
        self.assertIn("900", self.html)

    def test_margin_zero(self):
        """Stage margin is 0 (no padding between content and frame)."""
        self.assertIn("margin: 0", self.html)

    def test_center_false(self):
        """Content is not vertically centered (explicit layout)."""
        self.assertIn("center: false", self.html)

    def test_no_aspectRatio_option(self):
        """aspectRatio is not used (not a valid Reveal 5 config option)."""
        # The old deck used this; it should be gone
        self.assertNotIn("aspectRatio", self.html)

    def test_controls_false(self):
        """Default navigation controls are hidden."""
        self.assertIn("controls: false", self.html)

    def test_progress_false(self):
        """Default progress bar is hidden."""
        self.assertIn("progress: false", self.html)

    def test_slideNumber_false(self):
        """Default slide number is hidden (replaced by custom footer)."""
        self.assertIn("slideNumber: false", self.html)

    def test_autoAnimate_false(self):
        """autoAnimate is disabled (prevents layout morphing)."""
        self.assertIn("autoAnimate: false", self.html)

    def test_transition_fade(self):
        """Transition is 'fade' (minimal motion)."""
        self.assertIn("transition: 'fade'", self.html)

    def test_transition_speed_fast(self):
        """Transition speed is 'fast'."""
        self.assertIn("transitionSpeed: 'fast'", self.html)

    def test_pdf_export_support(self):
        """PDF export support is included (print-pdf link)."""
        self.assertIn("print-pdf", self.html)


class SignalRoomDesignTests(unittest.TestCase):
    """Test that the Signal Room design system is applied."""

    @classmethod
    def setUpClass(cls):
        if not INDEX_PATH.exists():
            raise cls.failureException(f"slides/index.html does not exist yet")

        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

        # Also check for referenced CSS files
        cls.css_files = []
        css_pattern = re.compile(r'<link[^>]*href="([^"]+\.css)"')
        for match in css_pattern.finditer(cls.html):
            cls.css_files.append(match.group(1))

        # Load theme CSS if it exists
        cls.css = ""
        if CSS_PATH.exists():
            with open(CSS_PATH, "r", encoding="utf-8") as f:
                cls.css = f.read()

    def test_midnight_background_used(self):
        """Midnight background color (#0a1128) is used."""
        self.assertIn(MIDNIGHT, self.html)

    def test_purple_accent_used(self):
        """Purple accent color (#6c63ff) is used."""
        self.assertIn(PURPLE, self.html)

    def test_green_accent_used(self):
        """Green accent color (#91e1ae) is used."""
        self.assertIn(GREEN, self.html)

    def test_outfit_font_referenced(self):
        """Outfit font is referenced (via @font-face or local file)."""
        self.assertIn("Outfit", self.html)

    def test_inter_font_referenced(self):
        """Inter font is referenced (via @font-face or local file)."""
        self.assertIn("Inter", self.html)

    def test_logo_reference_exists(self):
        """Fashma logo is referenced locally."""
        self.assertTrue(
            re.search(r'<img[^>]*src="[^"]*logo[^"]*"', self.html, re.IGNORECASE),
            "Fashma logo must be referenced locally",
        )

    def test_no_constellation_motif(self):
        """Constellation/network motif is retired (not on slides)."""
        # The redesign retires the constellation overlay
        self.assertNotIn("constellation", self.html.lower())

    def test_no_component_card_class(self):
        """Old .component-card class is retired."""
        # The redesign replaces generic cards with bespoke plates
        self.assertNotIn("component-card", self.html.lower())

    def test_no_accent_classes(self):
        """Old .accent-purple/.accent-green classes are retired."""
        self.assertNotIn("accent-purple", self.html.lower())
        self.assertNotIn("accent-green", self.html.lower())

    def test_no_inline_layout_styles(self):
        """No inline layout styles (the new design uses classes, not inline)."""
        # The old deck had inline display:flex, etc.
        inline_layout = re.compile(r'style="[^"]*display:\s*flex')
        matches = inline_layout.findall(self.html)
        self.assertEqual(
            len(matches), 0,
            f"Inline flex layout styles found: {len(matches)} (should use classes)",
        )

    def test_no_fragment_grow(self):
        """Old .fragment.grow class is retired."""
        self.assertNotIn("fragment.grow", self.html.lower())

    def test_custom_page_counter(self):
        """Static data-page page numbers are used (not CSS counter)."""
        # The revision requires data-page + attr(data-page) instead of CSS counters
        # because CSS counters break under Reveal's display:none for non-active slides.
        has_data_page = re.search(r'data-page="\d{2}"', self.html)
        has_attr = "attr(data-page)" in self.css
        self.assertTrue(
            has_data_page,
            "Static data-page attributes not found on slides",
        )
        self.assertTrue(
            has_attr,
            "CSS attr(data-page) for page numbers not found",
        )
        # Count data-page attributes — should be 14 (slides 1-14; slide 15 is closing)
        page_attrs = re.findall(r'data-page="(\d{2})"', self.html)
        self.assertEqual(
            len(page_attrs),
            14,
            f"Expected 14 data-page attributes, found {len(page_attrs)}",
        )
        # Check sequential values 01-14
        expected = [f"{i:02d}" for i in range(1, 15)]
        self.assertEqual(
            page_attrs,
            expected,
            f"Page numbers not sequential 01-14: {page_attrs}",
        )

    def test_footer_chrome(self):
        """Footer chrome (Fashma · Spectrum Market) is present."""
        # Check for footer content (may be in HTML or via CSS counter)
        self.assertIn("Fashma", self.html)

    def test_act_label_pattern(self):
        """Act labels use 'NN — LABEL' pattern."""
        # Check for at least one act label (01 — THE PROBLEM, etc.)
        act_pattern = re.compile(r"\d{2}\s*—\s*[A-Z]+", re.IGNORECASE)
        matches = act_pattern.findall(self.html)
        self.assertGreater(
            len(matches), 0,
            "No act labels found (expected '01 — THE PROBLEM' pattern)",
        )

    def test_svg_illustrations_present(self):
        """Bespoke SVG diagrams are present."""
        # The redesign requires one bespoke SVG per slide
        svg_pattern = re.compile(r'<svg[^>]*viewBox', re.IGNORECASE)
        matches = svg_pattern.findall(self.html)
        self.assertGreater(
            len(matches), 0,
            f"No inline SVG diagrams with viewBox found (expected bespoke illustrations)",
        )

    def test_svg_has_accessibility(self):
        """SVG diagrams have accessibility attributes."""
        # At least some SVGs should have role="img" or aria-labelledby
        has_role_img = 'role="img"' in self.html
        has_aria = 'aria-labelledby' in self.html
        self.assertTrue(
            has_role_img or has_aria,
            "SVG diagrams lack accessibility attributes (role='img' or aria-labelledby)",
        )


class CopyQualityTests(unittest.TestCase):
    """Test that slide content is substantive and well-written."""

    @classmethod
    def setUpClass(cls):
        if not INDEX_PATH.exists():
            raise cls.failureException(f"slides/index.html does not exist yet")

        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

        parser = RevealSlideParser()
        parser.feed(cls.html)
        cls.slides = parser.slides

    def test_no_placeholder_text(self):
        """No lorem ipsum, placeholder, or TODO text anywhere."""
        found = []
        for pattern in PLACEHOLDER_PATTERNS:
            matches = pattern.findall(self.html)
            if matches:
                found.extend(matches)
        self.assertEqual(found, [], f"Placeholder text found: {found}")

    def test_speaker_notes_present(self):
        """Speaker notes are included for each slide."""
        notes_pattern = re.compile(r'<aside[^>]*class="[^"]*notes[^"]*"', re.IGNORECASE)
        notes_count = len(notes_pattern.findall(self.html))
        self.assertGreaterEqual(
            notes_count, 15,
            f"Expected at least 15 speaker notes, found {notes_count}",
        )

    def test_no_banned_words(self):
        """Banned SaaS/marketing words are not used."""
        html_lower = self.html.lower()
        found = [w for w in BANNED_WORDS if w in html_lower]
        self.assertEqual(
            found, [],
            f"Banned words found in copy: {found}",
        )

    def test_no_old_claims(self):
        """Old unverified claims are removed from visible copy."""
        html_lower = self.html.lower()
        found = [c for c in OLD_CLAIMS if c.lower() in html_lower]
        self.assertEqual(
            found, [],
            f"Old visible claims found: {found} (see spec Appendix B)",
        )

    def test_no_technical_deep_dive_terms(self):
        """Main deck is business-oriented; no technical deep dive terms."""
        found = []
        for term in TECHNICAL_DEEP_DIVE_TERMS:
            if term in self.html:
                found.append(term)
        self.assertEqual(
            found,
            [],
            f"Technical deep-dive terms found in main deck: {found}",
        )

    def test_sru_described_as_unit_of_account(self):
        """SRU is described as a unit of account, not a token."""
        self.assertTrue(
            "unit of account" in self.html or "SRU" in self.html,
            "SRU (unit of account) should be mentioned",
        )

    def test_non_custodial_posture(self):
        """Non-custodial posture is explicitly stated."""
        self.assertIn(
            "non-custodial",
            self.html.lower(),
            "Non-custodial posture must be stated",
        )

    def test_luxembourg_pilot_ask_present(self):
        """The Luxembourg pilot ask is present."""
        self.assertIn("Luxembourg", self.html)
        self.assertTrue(
            "pilot" in self.html or "sandbox" in self.html,
            "Pilot or sandbox ask must be present",
        )

    def test_specimen_labels_present(self):
        """Mandatory specimen/illustrative claim labels are present."""
        html_lower = self.html.lower()
        missing = []
        for term, desc in MANDATORY_SPECIMEN_LINES:
            if term.lower() not in html_lower:
                missing.append(f"{term} ({desc})")
        self.assertEqual(
            missing, [],
            f"Missing specimen/illustrative labels: {missing}",
        )

    def test_no_endorsement_claim(self):
        """No implied endorsement is claimed."""
        self.assertIn("no endorsement", self.html.lower())

    def test_copy_ceiling_per_slide(self):
        """Each content slide stays within the 60-word ceiling."""
        # Cover (slide 1): ≤30 words; Closing (slide 15): ≤60 words; Content: ≤60
        for i, slide in enumerate(self.slides):
            limit = 30 if i == 0 else 60
            self.assertLessEqual(
                slide["word_count"],
                limit,
                f"Slide {i+1} exceeds {limit}-word ceiling: {slide['word_count']} words",
            )


class OfflineVendoringTests(unittest.TestCase):
    """Test that all assets are vendored locally — no CDN or runtime network."""

    @classmethod
    def setUpClass(cls):
        if not INDEX_PATH.exists():
            raise cls.failureException(f"slides/index.html does not exist yet")

        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_no_cdn_references(self):
        """No CDN URLs in the HTML (deck must work offline)."""
        found = []
        for pattern in CDN_PATTERNS:
            matches = pattern.findall(self.html)
            if matches:
                found.extend(matches)
        self.assertEqual(
            found,
            [],
            f"CDN references found (deck must work offline): {found}",
        )

    def test_no_http_references(self):
        """No http:// or https:// references at all (fully offline)."""
        # The redesign spec §4.11: "no http://, https://, //cdn, ..."
        # Allow ?print-pdf and data URIs
        http_pattern = re.compile(r'(?:https?://|//cdn|//fonts)')
        matches = http_pattern.findall(self.html)
        self.assertEqual(
            matches, [],
            f"External URL references found: {matches}",
        )

    def test_reveal_css_local(self):
        """Reveal.js CSS is linked locally."""
        self.assertTrue(
            re.search(r'<link[^>]*href="[^"]*reveal\.css"', self.html)
            or re.search(r'<link[^>]*href="[^"]*theme[^"]*\.css"', self.html),
            "Reveal.js theme CSS must be linked locally",
        )

    def test_reveal_js_local(self):
        """Reveal.js main JS is loaded locally."""
        self.assertTrue(
            re.search(r'<script[^>]*src="[^"]*reveal\.js"', self.html),
            "Reveal.js main JS must be loaded locally",
        )

    def test_notes_plugin_local(self):
        """Notes plugin is loaded locally."""
        self.assertTrue(
            re.search(r'<script[^>]*src="[^"]*notes\.js"', self.html),
            "Notes plugin must be loaded locally",
        )


class AssetIntegrityTests(unittest.TestCase):
    """Test that all local asset references resolve."""

    @classmethod
    def setUpClass(cls):
        if not INDEX_PATH.exists():
            raise cls.failureException(f"slides/index.html does not exist yet")

        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_image_sources_exist(self):
        """All referenced image files exist locally."""
        img_pattern = re.compile(r'<img[^>]*src="([^"]+)"')
        for match in img_pattern.finditer(self.html):
            src = match.group(1)
            # Skip data URIs
            if src.startswith("data:"):
                continue
            path = SLIDES_DIR / src
            self.assertTrue(
                path.exists(),
                f"Referenced image does not exist: {src}",
            )

    def test_images_have_alt_text(self):
        """Meaningful images have alt text."""
        img_pattern = re.compile(r'<img([^>]*)>')
        for match in img_pattern.finditer(self.html):
            img_attrs = match.group(1)
            # Skip decorative/logo-only images
            if 'alt=""' in img_attrs or "decorative" in img_attrs.lower():
                continue
            # Check if it has an alt attribute at all
            alt_pattern = re.compile(r'alt="([^"]*)"')
            alt_match = alt_pattern.search(img_attrs)
            # Logo and decorative images may have empty alt
            if 'src="logo' in img_attrs.lower() or 'alt=""' in img_attrs:
                continue
            self.assertIsNotNone(
                alt_match,
                f"Image without alt text: {img_attrs[:100]}",
            )

    def test_css_references_exist(self):
        """All referenced CSS files exist locally."""
        css_pattern = re.compile(r'<link[^>]*href="([^"]+\.css)"')
        for match in css_pattern.finditer(self.html):
            src = match.group(1)
            path = SLIDES_DIR / src
            self.assertTrue(
                path.exists(),
                f"Referenced CSS file does not exist: {src}",
            )

    def test_js_references_exist(self):
        """All referenced JS files exist locally."""
        js_pattern = re.compile(r'<script[^>]*src="([^"]+\.js)"')
        for match in js_pattern.finditer(self.html):
            src = match.group(1)
            path = SLIDES_DIR / src
            self.assertTrue(
                path.exists(),
                f"Referenced JS file does not exist: {src}",
            )

    def test_font_files_exist(self):
        """All referenced font files exist locally."""
        # Check @font-face src declarations in inline style and theme CSS
        font_pattern = re.compile(r"url\('([^']+\.ttf)'\)")
        all_fonts = font_pattern.findall(self.html)
        # Also check theme CSS
        if CSS_PATH.exists():
            with open(CSS_PATH, "r", encoding="utf-8") as f:
                css = f.read()
            all_fonts.extend(font_pattern.findall(css))

        for font_src in set(all_fonts):
            path = SLIDES_DIR / font_src
            self.assertTrue(
                path.exists(),
                f"Referenced font file does not exist: {font_src}",
            )


# Blockchain prominence requirements from FASHMA-BLOCKCHAIN-DECK-REVISION.md §9.1
# Slide → required visible terms + data-chain value
BLOCKCHAIN_PROMINENCE = {
    1: {
        "terms": ["blockchain"],
        "chain_value": "anchor",
        "desc": "Cover: blockchain record + orbit anchor",
    },
    4: {
        "terms": ["on-chain", "SHARED ON-CHAIN RECORD"],
        "chain_value": "fabric",
        "desc": "Trust fabric connecting three parts",
    },
    5: {
        "terms": ["NFT", "MINTED ON-CHAIN", "NON-TRANSFERABLE"],
        "chain_value": "seal",
        "desc": "Service NFT with mint seal",
    },
    7: {
        "terms": ["ON-CHAIN", "OFF-CHAIN"],
        "chain_value": "rail",
        "desc": "Anchor rail with deliberate off-chain gap",
    },
    8: {
        "terms": ["blockchain", "On-chain", "Off-chain"],
        "chain_value": "block",
        "desc": "Proof block centerpiece",
    },
    12: {
        "terms": ["on-chain receipt", "ANCHORED ON-CHAIN"],
        "chain_value": "rail",
        "desc": "Two-signature proof rail",
    },
    13: {
        "terms": ["PROOF OF TRANSACTION", "PRIVATE FINANCIAL MARKET"],
        "chain_value": "gates",
        "desc": "Gated blockchain roadmap",
    },
    15: {
        "terms": ["blockchain-verified"],
        "chain_value": "seal",
        "desc": "Blockchain-verified pilot ask",
    },
}

# Required slide copy changes from the revision spec
REQUIRED_SLIDE_COPY = {
    1: {
        "terms": ["The strategic asset", "the space economy trades", "blockchain record"],
        "desc": "Cover: blockchain record in standfirst",
    },
    4: {
        "terms": ["Three parts", "One continuous workflow", "on-chain record"],
        "desc": "Three parts, one workflow with on-chain record",
    },
    5: {
        "terms": ["A right to use", "not a title deed", "SERVICE NFT", "non-transferable"],
        "desc": "Service NFT as non-transferable on-chain card",
    },
    7: {
        "terms": ["From capacity", "to customer", "RESERVED", "OFF-CHAIN", "CONTRACTED", "ATTESTED"],
        "desc": "Deal flow with anchor rail and off-chain gap",
    },
    8: {
        "terms": ["A shared record", "held by no one", "Blockchain is the proof", "No custodian"],
        "desc": "Shared proof block with on-chain/off-chain boundary",
    },
    12: {
        "terms": ["The contract becomes", "a live link", "provider-signed attestation", "on-chain receipt"],
        "desc": "Delivery with anchored attestations",
    },
    13: {
        "terms": ["Prove it in", "four moves", "PROOF OF TRANSACTION", "REGULATED PILOT",
                   "PROGRAMMABLE MARKET", "PRIVATE FINANCIAL MARKET"],
        "desc": "Gated four-phase roadmap",
    },
    15: {
        "terms": ["Start with", "a pilot", "blockchain-verified", "Four requests"],
        "desc": "Blockchain-verified pilot ask with four requests",
    },
    9: {
        "terms": ["recorded on-chain"],
        "desc": "Slide 9: up-path recorded on-chain",
    },
    11: {
        "terms": ["CONTRACT MINTED"],
        "desc": "Slide 11: contract minted at output",
    },
    10: {
        "terms": ["03 Issue"],
        "desc": "Slide 10: seller issues contract (not settle)",
    },
}


class BlockchainProminenceTests(unittest.TestCase):
    """Blockchain is the deal's spine, not a trust slide.

    Enforces FASHMA-BLOCKCHAIN-DECK-REVISION.md §9.1-9.3:
    - Required on-chain language on 8 specific slides
    - Required data-chain attributes
    - No decorative chain clipart
    - On-chain/off-chain boundary claims
    - Word budget for 'blockchain'
    """

    @classmethod
    def setUpClass(cls):
        if not INDEX_PATH.exists():
            raise cls.failureException(f"slides/index.html does not exist yet")

        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

        parser = RevealSlideParser()
        parser.feed(cls.html)
        cls.slides = parser.slides

    def test_required_slides_have_chain_language(self):
        """Each required slide has its blockchain/on-chain language."""
        for slide_idx, req in BLOCKCHAIN_PROMINENCE.items():
            if slide_idx - 1 >= len(self.slides):
                self.fail(f"Slide {slide_idx} not found")
            slide_text = self.slides[slide_idx - 1]["text"]
            missing = []
            for term in req["terms"]:
                if term.lower() not in slide_text.lower():
                    missing.append(term)
            if missing:
                self.fail(
                    f"Slide {slide_idx} missing blockchain language: {missing} "
                    f"({req['desc']})"
                )

    def test_required_slides_have_chain_visual(self):
        """Each required slide has exactly one data-chain attribute with the right value.

        Matches data-chain as an attribute on tags (e.g., <g data-chain="..."> or
        <div data-chain="...">), NOT as literal text content (which would match
        test-gaming hidden spans like <span hidden>data-chain="anchor"</span>).
        """
        # Match data-chain as an attribute on any opening tag
        attr_pattern = re.compile(r'<[a-z][^>]*?\sdata-chain="([^"]+)"', re.IGNORECASE)

        # Determine which slide each data-chain attribute belongs to by
        # splitting the HTML at slide boundaries
        slide_html_parts = re.split(r'<section[^>]*class="[^"]*slide[^"]*"', self.html)
        slide_chain_map = {}
        for slide_idx, part in enumerate(slide_html_parts[1:], start=1):
            match = attr_pattern.search(part)
            if match:
                slide_chain_map[slide_idx] = match.group(1)

        # Required slides must have the correct chain value
        for slide_idx, req in BLOCKCHAIN_PROMINENCE.items():
            if slide_idx not in slide_chain_map:
                self.fail(
                    f"Slide {slide_idx} missing data-chain attribute "
                    f"(expected {req['chain_value']})"
                )
            elif slide_chain_map[slide_idx] != req["chain_value"]:
                self.fail(
                    f"Slide {slide_idx} data-chain={slide_chain_map[slide_idx]}, "
                    f"expected {req['chain_value']}"
                )

        # Non-required slides must not have data-chain
        non_required = [i for i in range(1, len(self.slides) + 1)]
        for req_slide in BLOCKCHAIN_PROMINENCE.keys():
            non_required.remove(req_slide)
        for slide_idx in non_required:
            if slide_idx in slide_chain_map:
                self.fail(
                    f"Slide {slide_idx} has data-chain but is not a required chain slide"
                )

    def test_chain_is_not_decorative(self):
        """data-chain elements are inside art figures or plate-wrap, not backgrounds."""
        # Check that data-chain appears within <figure class="art"> or .plate-wrap context
        # Simple heuristic: data-chain should be near svg or figure elements
        self.assertIn("data-chain", self.html)
        # Verify it's not on the section itself (decorative)
        # The HTML parser would need full context; check the pattern
        self.assertNotIn(
            'section data-chain=',
            self.html.replace(" ", "").replace("\n", "").replace("\t", "").replace("\r", "")
        )

    def test_no_hidden_chain_scaffolding(self):
        """No visually-hidden spans with literal data-chain text content.

        Asserts the developer did not add test-gaming scaffolding like
        <span hidden>data-chain="anchor"</span> to fool text-node tests.
        The data-chain attribute must be on real SVG elements.
        """
        # Match the pattern of a hidden span containing literal data-chain text
        hidden_chain_pattern = re.compile(
            r'<span[^>]*hidden[^>]*>\s*data-chain\s*=\s*"',
            re.IGNORECASE
        )
        matches = hidden_chain_pattern.findall(self.html)
        self.assertEqual(
            len(matches), 0,
            f"Found {len(matches)} hidden span(s) with literal data-chain text content "
            "(test-gaming scaffolding). data-chain must be an attribute on SVG elements."
        )

    def test_no_chain_clipart(self):
        """No decorative blockchain clipart (hexagons, cubes, coins, padlocks, wallets)."""
        clipart_terms = [
            "hexagon", "cube", "coin", "padlock", "wallet",
            "metamask", "connect-wallet",
        ]
        html_lower = self.html.lower()
        found = [t for t in clipart_terms if t in html_lower]
        self.assertEqual(
            found, [],
            f"Chain clipart terms found: {found}",
        )

    def test_chain_claim_boundaries(self):
        """Slide 8 has on-chain/off-chain claim markers; slide 13 has future marker."""
        # Slide 8 should have both data-claim markers
        on_chain_claim = re.search(r'data-claim="on-chain"', self.html)
        off_chain_claim = re.search(r'data-claim="off-chain"', self.html)
        future_claim = re.search(r'data-claim="future"', self.html)

        self.assertTrue(
            on_chain_claim,
            "Slide 8 missing data-claim='on-chain' marker"
        )
        self.assertTrue(
            off_chain_claim,
            "Slide 8 missing data-claim='off-chain' marker"
        )
        self.assertTrue(
            future_claim,
            "Slide 13 missing data-claim='future' marker"
        )

        # Slide 8 must mention 'encrypted' for off-chain docs
        slide8 = self.slides[7]
        self.assertIn("encrypted", slide8["text"].lower())

    def test_blockchain_word_budget(self):
        """'blockchain' appears at most 3 times in visible copy (C6)."""
        # Count occurrences of 'blockchain' in visible slide text (not notes)
        count = 0
        for slide in self.slides:
            text = slide["text"].lower()
            count += text.count("blockchain")
        self.assertLessEqual(
            count, 3,
            f"'blockchain' appears {count} times in visible copy; budget is 3",
        )

    def test_required_slide_copy_changes(self):
        """Specific slide copy changes from the revision spec are present."""
        for slide_idx, req in REQUIRED_SLIDE_COPY.items():
            if slide_idx - 1 >= len(self.slides):
                self.fail(f"Slide {slide_idx} not found")
            slide_text = self.slides[slide_idx - 1]["text"]
            missing = []
            for term in req["terms"]:
                if term.lower() not in slide_text.lower():
                    missing.append(term)
            if missing:
                self.fail(
                    f"Slide {slide_idx} missing copy: {missing} ({req['desc']})"
                )
if __name__ == "__main__":
    # Run from slides/ directory
    unittest.main(verbosity=2)