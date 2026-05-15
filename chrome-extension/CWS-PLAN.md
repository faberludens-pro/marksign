# MarkSign Panel — Chrome Web Store Publication Plan

**Product:** MarkSign Panel (Chrome Extension)
**Goal:** Publish as official Chrome Web Store extension
**Started:** 2026-04-26
**Extension source:** Originally at `~/.gemini/antigravity/scratch/webpage-to-markdown/`
**Canonical path:** `Projects/faberludenspro-marksign/chrome-extension/`

---

## Restoration prompt

> "Continue CWS submission for MarkSign Panel Chrome extension. Plan is at Projects/faberludenspro-marksign/chrome-extension/CWS-PLAN.md. Phase 1 cleanup is complete. Next: Phase 2 (store assets) and Phase 3 (submission)."

---

## Phase 1 — Code cleanup & hardening ✅ COMPLETE (2026-04-26)

- [x] **1.1** Moved to canonical path: `Projects/faberludenspro-marksign/chrome-extension/`
- [x] **1.2** Removed unused `lib/` (mammoth.js, pdf.js, xlsx.js — 4 MB bloat)
- [x] **1.3** Excluded `test-page.html`, `.DS_Store`, `README.md` from production package
- [x] **1.4** Fixed icons: center-cropped to square, converted to PNG, generated 16/32/48/128 px
- [x] **1.5** Updated `manifest.json`: `short_name`, `homepage_url`, `author`, all 4 icon sizes, corrected `default_title`
- [x] **1.6** Permission justification text prepared (see below)

### Permission justification (for CWS submission form)

> **activeTab + scripting:** MarkSign Panel reads the HTML of the currently active tab solely to convert its content to Markdown. The content is processed entirely on the user's device. No data is transmitted to any external server.

---

## Phase 2 — Store assets ⏳ PENDING

### 2.1 Screenshots (required — min 1, max 5)
- Size: **1280×800 px** (preferred) or 640×400 px, PNG or JPEG
- Suggested shots:
  1. Side panel open on a news article — full Chrome window
  2. Markdown preview after conversion
  3. Download prompt with filename
- Tool: Screenshot Chrome window, crop to 1280×800 in Preview or Figma

### 2.2 Promotional tile (optional)
- Small tile: **440×280 px**
- Use MarkSign brand colors + "Convert any webpage to Markdown" tagline

### 2.3 Store description

**Short (132 chars max):**
```
Convert any webpage to clean Markdown. Click Convert, preview, copy or download — right from Chrome's side panel.
```

**Full description (paste into Developer Dashboard):**
```
MarkSign Panel converts any webpage to clean, readable Markdown in one click — right inside Chrome's side panel.

✨ FEATURES
• One-click conversion — click Convert Page, get Markdown instantly
• Smart extraction — Mozilla Readability removes ads, navigation, and clutter
• Live preview — see the Markdown before you copy or save
• Copy to clipboard — paste anywhere in seconds
• Download as .md file — auto-named from the page title
• Metadata footer — title and source URL appended automatically
• Light & dark theme — follows your system preference

📝 HOW IT WORKS
1. Click the MarkSign icon in your Chrome toolbar to open the side panel
2. Navigate to any article, documentation page, or blog post
3. Click "Convert Page"
4. Copy or download the clean Markdown

🔒 PRIVACY
MarkSign Panel processes your page entirely on your device. No data is sent to any server. No account required.

Built by Faber-Ludens Pro — marksign.faberludens.pro
```

### 2.4 Privacy policy (required)
- Need a live URL before submitting
- Minimum content: extension reads active tab HTML locally; no data leaves the device; no analytics; no accounts
- Options: GitHub Pages (`faberludens-pro.github.io/marksign/privacy`) or a page on `faberludens.pro`
- **Status: PENDING** — write and publish before submission

### 2.5 Category and metadata
- Category: **Productivity**
- Language: English
- Website: https://marksign.faberludens.pro

---

## Phase 3 — Developer account & submission ⏳ PENDING

### 3.1 Chrome Web Store developer account
- URL: https://chrome.google.com/webstore/devconsole
- One-time fee: **$5 USD**
- Use: **faberludens.pro Google account** (not personal Gmail)
- Status: **PENDING** — confirm account exists or create

### 3.2 Package the extension
Run from `chrome-extension/` folder:
```bash
cd "Projects/faberludenspro-marksign/chrome-extension"
zip -r marksign-panel-v1.0.0.zip manifest.json background.js sidepanel.html sidepanel.js styles.css turndown.js Readability.js icons/
```
The `.zip` file is gitignored — do not commit it.

### 3.3 Submit on Developer Dashboard
1. Go to Developer Dashboard → Add new item
2. Upload `marksign-panel-v1.0.0.zip`
3. Fill in: description, screenshots, privacy policy URL, category
4. Permissions justification: paste text from Phase 1.6
5. Declare: "This extension does not collect or transmit user data"
6. Submit for review

### 3.4 Review timeline
- First-time submissions: **3–7 business days**
- `scripting` permission may trigger manual review: expect 5–7 days
- Monitor email associated with the CWS developer account

---

## Phase 4 — Post-publication ⏳ FUTURE

- [ ] Add Chrome extension `manifest.json` to the MarkSign 4-file version bump checklist
- [ ] Set up Google Analytics 4 in Developer Dashboard for install tracking
- [ ] Add "Available on Chrome Web Store" badge to MarkSign landing page
- [ ] Plan Part 2: embed panel as feature in MarkSign macOS app

---

## File inventory (production package)

```
chrome-extension/
├── manifest.json        # ✅ Updated: short_name, author, homepage_url, all icon sizes
├── background.js        # ✅ Service worker
├── sidepanel.html       # ✅ UI
├── sidepanel.js         # ✅ Conversion logic
├── styles.css           # ✅ Light/dark theme
├── turndown.js          # ✅ HTML→Markdown library (Turndown v7.1.2)
├── Readability.js       # ✅ Mozilla Readability (content extraction)
├── icons/
│   ├── icon16.png       # ✅ Square PNG 16×16
│   ├── icon32.png       # ✅ Square PNG 32×32
│   ├── icon48.png       # ✅ Square PNG 48×48
│   └── icon128.png      # ✅ Square PNG 128×128
├── CWS-PLAN.md          # This file — not included in .zip
└── .gitignore           # Not included in .zip
```

---

## What you need to do (human steps)

1. **Visually verify icons** — open `icons/` in Finder and confirm they look correct at each size
2. **Write and publish privacy policy** — minimum one-paragraph page at a live URL
3. **Create/confirm CWS developer account** — $5 fee, use faberludens.pro Google account
4. **Take screenshots** — 1280×800 px Chrome window with extension in use
5. **Run the zip command** (Phase 3.2) and submit

Everything else is done.
