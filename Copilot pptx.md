---
name: pptx
description: "Use this skill for ALL PowerPoint presentations. Overrides the base pptx skill. Always outputs a self-contained Node.js script (not a .pptx file directly) that the user runs locally. Enforces the user's brand, their preferred modern web/Figma aesthetic (diagonal-cut panels, clean sans-serif, deep navy + accent, generous whitespace, asymmetric layouts), and auto-installs all required npm packages at the top of the generated script."
---

# PPTX Skill

This skill governs **every** presentation the user creates. It overrides the base pptx skill on all points where they conflict.

---

## Output Mode: Always JS, Never Direct PPTX

**Never generate a `.pptx` file directly from Claude's environment.**
Always output a complete, self-contained `build.js` Node.js script that the user runs on their own machine. The script must:

1. Auto-install all required npm packages if not already present (see Dependency Bootstrap below)
2. Generate the `.pptx` using `pptxgenjs`
3. Save the output file to the same directory as the script

Present the script as a downloadable artifact. After presenting it, tell the user:
> "Save this as `build.js` in a folder of your choice, then run `node build.js` to generate the presentation."

---

## Dependency Bootstrap (always at top of every script)

Every generated script must begin with this exact block before any presentation code:

```javascript
// ─── Auto-install dependencies ────────────────────────────────────────────────
const { execSync } = require("child_process");

function ensurePackage(pkg) {
  try {
    require.resolve(pkg);
  } catch {
    console.log(`Installing ${pkg}...`);
    execSync(`npm install ${pkg}`, { stdio: "inherit" });
  }
}

ensurePackage("pptxgenjs");
ensurePackage("react");
ensurePackage("react-dom");
ensurePackage("react-icons");
ensurePackage("sharp");
// ──────────────────────────────────────────────────────────────────────────────

const pptxgen  = require("pptxgenjs");
const React    = require("react");
const ReactDOM = require("react-dom/server");
const sharp    = require("sharp");
const path     = require("path");
const fs       = require("fs");
```

---

## Brand

### Logo

**Path (hardcoded, never change):**
```
C:/xxxxxx/one-drive/Design Assets/logo.svg
```

**Cropping:** The SVG viewBox is 560×400 but the visible content (eagle + wordmark) occupies only the centre strip: approximately x=50, y=161, w=459, h=78 in SVG units. Apply `sizing.type: "crop"` to strip the whitespace:

```javascript
// Logo — crop to content, strip surrounding whitespace
function addLogo(slide, opts = {}) {
  const logoPath = "C:/xxxxxxx/one-drive/Design Assets/logo.svg";
  const displayW = opts.w || 1.6;       // display width in inches
  const aspectH  = displayW * (78 / 459); // maintain content aspect ratio
  const displayH = opts.h || aspectH;

  slide.addImage({
    path: logoPath,
    x: opts.x !== undefined ? opts.x : 0.5,
    y: opts.y !== undefined ? opts.y : 0.2,
    w: displayW,
    h: displayH,
    // Crop to the visible content region, stripping whitespace
    sizing: {
      type: "crop",
      x: 50  / 560,        // left whitespace fraction
      y: 161 / 400,        // top whitespace fraction
      w: 459 / 560,        // content width fraction
      h: 78  / 400,        // content height fraction
    }
  });
}
```

**Placement rules:**
- Every slide gets the logo — no exceptions.
- **Light slides** (white/near-white background): logo at top-left, x=0.55, y=0.22, w=1.5
- **Dark slides** (navy background): logo at top-left, x=0.55, y=0.22, w=1.5 — the eagle's cyan (`#00AEEF`) is visible on navy, no modification needed
- Never place the logo over busy content or coloured panels where the cyan would be lost
- Maintain a clear zone of at least 0.25" around the logo on all sides

### Brand Colours

```javascript
// ── Brand Palette ────────────────────────────────────────────────────────────
const NAVY    = "0B1B38";   // Deep navy — primary (~65% visual weight)
const NAVY2   = "13294E";   // Lighter navy — layered panels / cards on dark bg
const NAVY3   = "1C3868";   // Mid navy — diagonal motif layers, subtle depth
const CYAN    = "00AEEF";   // Eagle cyan — the ONE accent colour
const CYAN_D  = "0091AD";   // Deeper cyan — eyebrow labels on light backgrounds
const WHITE   = "FFFFFF";
const OFFWHT  = "FAFBFC";   // Near-white — light slide backgrounds
const INK     = "0B1B38";   // Body text on light backgrounds (reuse NAVY)
const MUTED   = "6B7587";   // Subtext / captions on light backgrounds
const MUTED_L = "8E9AB8";   // Subtext on dark/navy backgrounds
const LINE    = "E8EAEE";   // Dividers on light backgrounds
// ────────────────────────────────────────────────────────────────────────────
```

The brand cyan (`00AEEF`) replaces every generic "accent" colour in every slide. Never use gold, orange, red, green, or any other accent — materials use exactly one accent colour.

---

## Aesthetic: Modern Web / Figma Style

This is **non-negotiable** — every deck must follow this design language. It was established in the Investment Banking Overview presentation the user approved.

### The Core Motif: Diagonal-Cut Panels

Use `CUSTOM_GEOMETRY` with a `points` array to create angled polygon panels — NOT plain rectangles. This is the single most important visual signature.

```javascript
// Example: diagonal hero split (title / closing slides)
// Right ~45% of slide is navy, cut in at an angle from top-left to bottom-left
slide.addShape(pres.shapes.CUSTOM_GEOMETRY, {
  x: 0, y: 0, w: SW, h: SH,
  points: [
    { x: 8.6, y: 0,  moveTo: true },  // top of the diagonal cut
    { x: SW,  y: 0  },
    { x: SW,  y: SH },
    { x: 6.5, y: SH },                // bottom of the diagonal cut
    { close: true }
  ],
  fill: { color: NAVY },
  line: { type: "none" }
});

// Example: chevron two-panel split (content slides)
// Left panel with angled right edge, right panel overlapping to form a seam
slide.addShape(pres.shapes.CUSTOM_GEOMETRY, {
  x: 0, y: panelY, w: 7.0, h: panelH,
  points: [
    { x: 0,   y: 0,      moveTo: true },
    { x: 7.0, y: 0      },
    { x: 6.3, y: panelH },
    { x: 0,   y: panelH },
    { close: true }
  ],
  fill: { color: WHITE },
  line: { color: LINE, width: 1 }
});
```

**Use diagonal panels on:**
- Title slide — full-height diagonal split, white left / navy right
- Closing / summary slide — mirrored diagonal, bookending the title
- Side-by-side comparison slides — chevron seam between the two panels
- Call-out or emphasis panels within content slides

**Use rectangular shapes for:**
- Individual cards within a panel (not full-bleed elements)
- Small accent corner tabs (see below)

### Accent Corner Tabs

A small `0.5 × 0.5"` cyan square at the top-left corner of a card signals it as a featured/primary card. Use sparingly — one per slide maximum.

```javascript
slide.addShape(pres.shapes.RECTANGLE, {
  x: cardX, y: cardY, w: 0.5, h: 0.5,
  fill: { color: CYAN }, line: { type: "none" }
});
```

### Nav-Style Eyebrow Labels

Every slide (except title/closing) gets a small-caps tracked-out section label above the main heading:

```javascript
function eyebrow(slide, text, x, y, opts = {}) {
  slide.addText(text.toUpperCase(), {
    x, y, w: opts.w || 7, h: 0.32,
    fontFace: "Calibri", fontSize: 11, bold: true,
    color: opts.dark ? CYAN : CYAN_D,
    charSpacing: 3, margin: 0
  });
}
```

### Nav-Style List Markers

Replace bullet points with a short cyan rule mark — matches the "OUR SERVICES — TERMINALS MAP" pattern from the reference sites:

```javascript
function navMark(slide, x, y, dark) {
  slide.addShape(pres.shapes.LINE, {
    x, y, w: 0.35, h: 0,
    line: { color: dark ? CYAN : CYAN_D, width: 1.5 }
  });
}
// Usage: navMark(slide, 0.7, itemY + 0.13, false); then addText at x+0.5
```

### Page Numbers

```javascript
function pageNum(slide, n, total, dark) {
  slide.addText([
    { text: String(n).padStart(2,"0"), options: { color: dark ? WHITE : INK, bold: true } },
    { text: ` / ${String(total).padStart(2,"0")}`, options: { color: dark ? MUTED_L : MUTED } }
  ], {
    x: SW - 1.3, y: SH - 0.55, w: 1.0, h: 0.3,
    fontFace: "Calibri", fontSize: 9.5, align: "right", margin: 0
  });
}
```

---

## Typography

**Typeface:** Calibri throughout — no exceptions, no serifs.

| Element | Size | Weight | Notes |
|---------|------|--------|-------|
| Hero / title | 48–56pt | Bold | Line-height ~1.0; let it take up space |
| Slide heading | 28–34pt | Bold | Two lines max |
| Eyebrow label | 11pt | Bold | All-caps, charSpacing: 3 |
| Sub-heading | 16–18pt | Bold | |
| Body / description | 11–13pt | Regular | lineSpacingMultiple: 1.25–1.3 |
| Caption / footnote | 9–10pt | Regular | Italic for disclaimers |
| Card number (01, 02…) | 18–22pt | Bold | Cyan accent colour |
| Page number | 9.5pt | Mixed | See pageNum() above |

**Weight contrast is the primary typographic tool** — bold oversized headlines against light small body text. Never put two elements of similar weight next to each other.

**Never use Aptos, Georgia, Trebuchet MS, or any non-Calibri font.**

---

## Layout System

### Slide Dimensions

```javascript
pres.layout = "LAYOUT_WIDE"; // 13.3" × 7.5"
const SW = 13.3, SH = 7.5;
```

### Margin & Spacing Rules

- Minimum 0.65" from any slide edge to content (slightly more than the base skill's 0.5" — gives the premium feel)
- 0.3" gap between content blocks minimum; 0.5" preferred
- Logo zone: top 0.2–0.6" of slide, left-aligned — content starts below y=0.8
- Page number zone: bottom-right, y=SH-0.55 — leave clear

### Slide Structure: "Sandwich" Model

| Slide type | Background | When to use |
|------------|-----------|-------------|
| Title | White left / navy diagonal right | First slide |
| Content (most slides) | White or `OFFWHT` | Facts, divisions, lists |
| Dark feature | Full navy | League tables, emphasis grids, key stats |
| Closing | Full navy with diagonal accent | Last slide |

Alternate between white and navy content slides where possible — don't run more than two consecutive slides of the same background.

### Layout Vocabulary (vary across slides — never repeat the same layout twice)

| Name | Description |
|------|-------------|
| **Diagonal hero** | White + navy diagonal split, content on left, accent words on right |
| **Chevron split** | Two panels meeting at an angled seam (sell-side/buy-side style) |
| **Float card** | Large navy card floating on white, with accent corner tab |
| **Numbered grid** | 3 or 4 cards, alternating vertical offsets, cyan "01/02…" number top-left |
| **Offset rows** | Horizontal rows with alternating indent (left-flush / indented) |
| **Stat callout** | Giant number (60–72pt) + small label, white space around it |
| **Timeline** | Numbered steps with cyan marks and connecting lines |

---

## Icon System

Use `react-icons/fa` (Font Awesome). Always rasterize to PNG via `sharp` — do NOT embed SVG directly in pptxgenjs.

### Icon Helper (include in every script)

```javascript
// ── Icon helpers ─────────────────────────────────────────────────────────────
async function iconPng(IconComponent, hexColor, sizePx = 256) {
  // Replace currentColor with literal hex so sharp/librsvg resolves fills correctly
  let svg = ReactDOM.renderToStaticMarkup(
    React.createElement(IconComponent, { color: hexColor, size: String(sizePx) })
  );
  svg = svg.split("currentColor").join(hexColor);
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

function iconCircle(slide, iconData, cx, cy, diameter, circleFill) {
  const r = diameter / 2;
  slide.addShape(pres.shapes.OVAL, {
    x: cx - r, y: cy - r, w: diameter, h: diameter,
    fill: { color: circleFill }, line: { type: "none" }
  });
  const isz = diameter * 0.52;
  slide.addImage({ data: iconData, x: cx - isz/2, y: cy - isz/2, w: isz, h: isz });
}
// ─────────────────────────────────────────────────────────────────────────────
```

### Icon Colour Rules

| Background of host element | Circle fill | Icon colour |
|---------------------------|-------------|-------------|
| White / OFFWHT slide | `NAVY` | `#FFFFFF` |
| Navy card / panel | `CYAN` | `#0B1B38` (navy) |
| Accent (cyan) element | `NAVY` | `#FFFFFF` |

**Never use a dark icon on a dark background or a light icon on a light background.**

Always generate icon PNGs with `#FFFFFF` or `#0B1B38` — never cyan for the icon itself (reserved for circle backgrounds and text accents).

---

## Shadow System

**Always use a factory function** — pptxgenjs mutates shadow objects in-place and reusing one object corrupts subsequent shapes:

```javascript
const shadowSm  = () => ({ type: "outer", color: "0B1B38", blur: 14, offset: 4, angle: 90, opacity: 0.10 });
const shadowMd  = () => ({ type: "outer", color: "0B1B38", blur: 24, offset: 7, angle: 90, opacity: 0.13 });
const shadowLg  = () => ({ type: "outer", color: "0B1B38", blur: 36, offset: 10, angle: 90, opacity: 0.15 });
```

- Use `shadowSm` on small cards and icon circles
- Use `shadowMd` on the main floating card per slide
- Use `shadowLg` on hero panels when a slide has a single dominant element
- **Never add shadows to diagonal custom-geometry panels** — they render incorrectly in LibreOffice and add noise

---

## Colour Safety Rules

Critical pitfalls that corrupt the `.pptx` file — enforce in every script:

```javascript
// ✅ CORRECT — no # prefix
color: "00AEEF"
fill: { color: "0B1B38" }

// ❌ WRONG — corrupts file
color: "#00AEEF"

// ✅ CORRECT — opacity as separate property
shadow: { type: "outer", blur: 14, offset: 4, color: "000000", opacity: 0.12 }

// ❌ WRONG — 8-char hex corrupts file
shadow: { type: "outer", blur: 14, offset: 4, color: "00000020" }
```

---

## Quality Checklist (run mentally before finalising every script)

### Content
- [ ] Every slide has a clear heading, eyebrow label (content slides), and body content
- [ ] No placeholder text (no "Lorem ipsum", "INSERT X", "TBC", etc.)
- [ ] Page numbers on all slides except title
- [ ] Company logo on every slide
- [ ] Footnotes / data sources included where stats are cited

### Design
- [ ] No two consecutive slides share the same layout
- [ ] At least one diagonal/custom-geometry element per deck (typically title + closing)
- [ ] Single accent colour (CYAN `00AEEF`) — no gold, orange, green, etc.
- [ ] All icons are white-on-navy or navy-on-cyan — no invisible combos
- [ ] No accent stripes spanning a full edge of any shape or slide
- [ ] No serif fonts — Calibri only
- [ ] Bold headlines vs light body: clear size contrast (≥2× font size ratio)

### Technical
- [ ] Every shadow object is created via a factory function (`shadowSm()`, not a shared const)
- [ ] No `#` prefix on any hex colour string
- [ ] `currentColor` replaced with literal hex before passing SVG to sharp
- [ ] Logo uses `sizing: { type: "crop", ... }` to strip whitespace
- [ ] Dependency bootstrap block is the first thing in the script
- [ ] Script ends with `pres.writeFile(...)` and prints the output path

---

## Complete Script Template

Every generated script must follow this skeleton:

```javascript
// ─── Auto-install dependencies ────────────────────────────────────────────────
const { execSync } = require("child_process");
function ensurePackage(pkg) {
  try { require.resolve(pkg); }
  catch { console.log(`Installing ${pkg}...`); execSync(`npm install ${pkg}`, { stdio: "inherit" }); }
}
ensurePackage("pptxgenjs");
ensurePackage("react");
ensurePackage("react-dom");
ensurePackage("react-icons");
ensurePackage("sharp");
// ──────────────────────────────────────────────────────────────────────────────

const pptxgen  = require("pptxgenjs");
const React    = require("react");
const ReactDOM = require("react-dom/server");
const sharp    = require("sharp");
const path     = require("path");
const fs       = require("fs");

// ── Icons (import only what this deck uses) ───────────────────────────────────
const { FaHandshake, FaChartLine /*, ... */ } = require("react-icons/fa");

// ── Brand palette ─────────────────────────────────────────────────────────────
const NAVY="0B1B38", NAVY2="13294E", NAVY3="1C3868";
const CYAN="00AEEF", CYAN_D="0091AD";
const WHITE="FFFFFF", OFFWHT="FAFBFC";
const INK="0B1B38", MUTED="6B7587", MUTED_L="8E9AB8", LINE="E8EAEE";
const FONT = "Calibri";

// ── Layout constants ──────────────────────────────────────────────────────────
const SW = 13.3, SH = 7.5;

// ── Shadow factories (never reuse object — pptxgenjs mutates in-place) ────────
const shadowSm = () => ({ type:"outer", color:"0B1B38", blur:14, offset:4, angle:90, opacity:0.10 });
const shadowMd = () => ({ type:"outer", color:"0B1B38", blur:24, offset:7, angle:90, opacity:0.13 });

// ── Icon helper ───────────────────────────────────────────────────────────────
async function iconPng(Icon, hex, px=256) {
  let svg = ReactDOM.renderToStaticMarkup(React.createElement(Icon, { color: hex, size: String(px) }));
  svg = svg.split("currentColor").join(hex);
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}
function iconCircle(slide, data, cx, cy, d, fill) {
  slide.addShape(pres.shapes.OVAL, { x:cx-d/2, y:cy-d/2, w:d, h:d, fill:{color:fill}, line:{type:"none"} });
  const s=d*0.52; slide.addImage({ data, x:cx-s/2, y:cy-s/2, w:s, h:s });
}

// ── Reusable helpers ──────────────────────────────────────────────────────────
function eyebrow(slide, text, x, y, dark=false, w=7) {
  slide.addText(text.toUpperCase(), { x, y, w, h:0.32, fontFace:FONT, fontSize:11, bold:true,
    color: dark ? CYAN : CYAN_D, charSpacing:3, margin:0 });
}
function pageNum(slide, n, total, dark=false) {
  slide.addText([
    { text: String(n).padStart(2,"0"), options:{ color: dark ? WHITE : INK, bold:true } },
    { text: ` / ${String(total).padStart(2,"0")}`, options:{ color: dark ? MUTED_L : MUTED } }
  ], { x:SW-1.3, y:SH-0.55, w:1.0, h:0.3, fontFace:FONT, fontSize:9.5, align:"right", margin:0 });
}
function navMark(slide, x, y, dark=false) {
  slide.addShape(pres.shapes.LINE, { x, y, w:0.35, h:0, line:{color: dark ? CYAN : CYAN_D, width:1.5} });
}
function addLogo(slide, x=0.55, y=0.22, w=1.5) {
  const logoPath = "C:/xxxxxxxx/one-drive/Design Assets/logo.svg";
  const h = w * (78/459); // content aspect ratio after crop
  slide.addImage({
    path: logoPath, x, y, w, h,
    sizing: { type:"crop", x:50/560, y:161/400, w:459/560, h:78/400 }
  });
}

// ── Presentation ──────────────────────────────────────────────────────────────
async function main() {
  let pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.author = "Author";
  pres.title  = "YOUR DECK TITLE";

  const TOTAL = /* number of slides */ 1;

  // ── SLIDE 1: Title ──────────────────────────────────────────────────────────
  {
    const s = pres.addSlide();
    s.background = { color: WHITE };

    // Diagonal navy panel (right ~48%)
    s.addShape(pres.shapes.CUSTOM_GEOMETRY, {
      x:0, y:0, w:SW, h:SH,
      points:[{x:8.6,y:0,moveTo:true},{x:SW,y:0},{x:SW,y:SH},{x:6.5,y:SH},{close:true}],
      fill:{ color:NAVY }, line:{ type:"none" }
    });
    // Subtle mid-navy sliver for depth
    s.addShape(pres.shapes.CUSTOM_GEOMETRY, {
      x:0, y:0, w:SW, h:SH,
      points:[{x:8.6,y:0,moveTo:true},{x:9.5,y:0},{x:7.4,y:SH},{x:6.5,y:SH},{close:true}],
      fill:{ color:NAVY3 }, line:{ type:"none" }
    });

    addLogo(s);  // top-left, on white
    eyebrow(s, "SECTION LABEL", 0.7, 2.2, false);
    s.addText("Main Title Here", {
      x:0.65, y:2.55, w:6, h:1.8, fontFace:FONT, fontSize:52, bold:true, color:INK, margin:0, lineSpacingMultiple:1.0
    });
    s.addText("Subtitle or descriptive sentence goes here.", {
      x:0.7, y:4.45, w:5.5, h:0.65, fontFace:FONT, fontSize:14, color:MUTED, margin:0, lineSpacingMultiple:1.25
    });

    // Right (navy) panel — accent words
    s.addText("KEYWORD", { x:9.45, y:1.8, w:3.3, h:0.3, fontFace:FONT, fontSize:10, bold:true, color:CYAN, charSpacing:2.5, margin:0 });
    s.addText("Key phrase.", { x:9.45, y:2.1, w:3.3, h:0.7, fontFace:FONT, fontSize:28, bold:true, color:WHITE, margin:0 });
    s.addText("Supporting line one.\nSupporting line two.", { x:9.45, y:2.9, w:3.3, h:0.9, fontFace:FONT, fontSize:18, color:MUTED_L, margin:0, lineSpacingMultiple:1.15 });
  }

  // ── Additional slides go here ───────────────────────────────────────────────

  // ── Write file ──────────────────────────────────────────────────────────────
  const outPath = path.join(__dirname, "Presentation.pptx");
  await pres.writeFile({ fileName: outPath });
  console.log(`\n✅  Saved: ${outPath}`);
}

main().catch(err => { console.error(err); process.exit(1); });
```

---

## Additional Best-in-Class Rules

### 1. Consistency Enforcement
- All text boxes on the same visual row must share the same `y` coordinate
- All cards in a grid must share the same `w` and `h` (unless intentionally staggered for rhythm)
- Staggered grids must have a clear rule (e.g. "odd columns are 0.25" taller")

### 2. Progressive Disclosure
- Title slide: topic + 3 anchor words — no body text
- Content slides: one idea per slide; split if a slide needs more than 3 bullets
- Closing slide: 4-point numbered summary only

### 3. Data & Numbers
- Any statistic gets a large callout (48–60pt) with a small label below — never buried in body text
- Charts use `chartColors: [CYAN, NAVY, NAVY3]` — never default blue/orange
- Chart grid lines: `valGridLine: { color: LINE, size: 0.5 }`, `catGridLine: { style: "none" }`

### 4. Slide-Level Self-Check (add as a comment block in the output script)
```javascript
/*
  Slide N — [LAYOUT NAME]
  Background: WHITE / NAVY
  Logo: ✓ top-left x=0.55 y=0.22
  Page number: ✓ / N/A (title slide)
  Diagonal element: ✓ / none (explain why)
  Accent colour used: cyan only ✓
  Shadow objects: fresh factory calls ✓
*/
```

### 5. File Naming
Output file name should be descriptive, title-cased, no spaces:
```javascript
const outPath = path.join(__dirname, "DeckTopic_YYYY.pptx");
```

### 6. Error Handling
Every script ends with a `.catch` block that logs clearly:
```javascript
main().catch(err => {
  console.error("\n❌  Build failed:", err.message);
  process.exit(1);
});
```

### 7. Logo File Missing — Graceful Warning
```javascript
function addLogo(slide, x=0.55, y=0.22, w=1.5) {
  const logoPath = "C:/xxxxxxx/one-drive/Design Assets/logo.svg";
  if (!fs.existsSync(logoPath)) {
    console.warn(`⚠️  Logo not found at: ${logoPath} — placeholder used`);
    // Fallback: text wordmark placeholder
    slide.addText("[LOGO]", { x, y, w, h:0.35, fontFace:FONT, fontSize:13, bold:true, color:CYAN, charSpacing:2, margin:0 });
    return;
  }
  const h = w * (78/459);
  slide.addImage({
    path: logoPath, x, y, w, h,
    sizing: { type:"crop", x:50/560, y:161/400, w:459/560, h:78/400 }
  });
}
```

---

## When Claude Generates a New Deck

1. Read this skill file first — every time, don't rely on memory
2. Ask the user for: topic, number of slides, any specific content/data, whether it's internal or client-facing
3. Plan the slide sequence before writing code (one line per slide: layout name + headline)
4. Write the full `build.js` script as a single artifact
5. Include the self-check comment block on each slide
6. Tell the user how to run it and what output file to expect
