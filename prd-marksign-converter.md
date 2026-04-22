# PRD — MarkSign Converter (Public macOS App)

**Version:** 1.0
**Date:** 2026-04-20
**Author:** Gonçalo Ferraz — Faber-Ludens Pro
**Status:** Approved for execution

---

## 1. Metadata

| Field | Value |
|-------|-------|
| Product name | MarkSign Converter |
| Product type | Native macOS utility app |
| Platform | macOS (Apple Silicon + Intel via Rosetta) |
| Distribution | Direct DMG — own landing page + GitHub Releases |
| Pricing model | One-time purchase (freemium in post-alpha phase) |
| MVP deadline | No hard deadline — ship when stable |
| Product owner | Gonçalo Ferraz |
| Stakeholders | Gonçalo Ferraz (founder, sole developer for alpha) |
| Related products | MarkSign Platform (separate initiative — digital signature); MarkSign Reader (companion viewer, ships in v1 DMG) |
| Engine source | Extracted from `biblios_brain.py` → `marksign_engine.py` |

---

## 2. Executive Summary

MarkSign Converter is a native macOS menu bar utility that converts documents (PDF, DOCX, PPTX, EPUB, XLSX, TXT, RTF) to structured Markdown. It targets knowledge workers and researchers who encounter files in Finder, email, or Downloads and need clean Markdown for notes apps, AI tools, or repositories — in one drag-and-drop.

The product ships as a DMG containing two apps: the Converter (menu bar only, no Dock icon) and MarkSign Reader (a companion Markdown viewer with Newsprint-style CSS). Both share a single installer. The engine is a local, zero-cost, multi-engine pipeline (docling → pymupdf → pandoc → markitdown) extracted from the existing `biblios_brain.py` codebase.

The strategic approach is A→B hybrid: validate the engine in isolation first, then build the minimum UI for alpha distribution. This mitigates the highest technical risk (docling extraction) before committing to UI work.

---

## 3. Context and Problem

### Problem

Knowledge workers, researchers, and developers regularly receive or discover documents in proprietary formats (PDF, DOCX, PPTX, EPUB, XLSX) that they cannot directly use with Markdown-based workflows — note-taking apps (Obsidian, Bear, Notion), AI assistants (Claude, ChatGPT), and code repositories. Converting these files today requires either:

- Web services that raise privacy concerns for sensitive documents (client specs, research papers, internal reports)
- Command-line tools with steep setup requirements
- Paid subscriptions to cloud converters with per-file or per-month billing

There is no native macOS converter that is local, free of recurring cost, and integrable with the Finder workflow.

### Opportunity

A native menu bar app with Finder right-click integration removes the friction entirely. The user encounters a file they want to convert, right-clicks, and MarkSign opens with the file pre-loaded. No command line. No web browser. No cloud upload.

The conversion engine already exists and has been validated through the Biblios project (`biblios_brain.py`). This PRD governs extracting it, packaging it, and shipping it as a standalone product.

### Current state

- Engine (`biblios_brain.py`): production-quality, tested across PDF/DOCX/EPUB/RTF formats; uses docling, pymupdf, pandoc, markitdown, libreoffice
- macOS Quick Action: exists as `marksign-convert.sh` → Automator (right-click, Quick Actions submenu)
- UI: HTML prototype complete through v4 (4 states: empty, files loaded, converting, done)
- App: not yet built — engine extraction and packaging are Phase 0

---

## 4. Goals and Non-Goals

### Goals

| # | Goal | Measure |
|---|------|---------|
| G1 | Convert the 7 supported formats (PDF, DOCX, PPTX, EPUB, XLSX, TXT, RTF) to Markdown with structural fidelity | Headings, lists, and tables preserved; conversion succeeds on reference test set |
| G2 | Integrates into the Finder workflow via top-level right-click context menu item | "Convert with MarkSign" appears at top level (not under Quick Actions submenu) |
| G3 | Output saved to the same folder as the source file by default | No configuration required for the primary use case |
| G4 | Menu bar app with no Dock icon while idle | Converter does not appear in Dock until window is open (macOS LSUIElement behaviour) |
| G5 | Ships with MarkSign Reader companion app in the same DMG | Reader installed alongside Converter; .md handler registration is opt-in |
| G6 | Docling engine downloaded on first run, not bundled | Base DMG ≤ 300 MB; docling download completes with progress feedback |

### Non-Goals (v1)

| Item | Disposition |
|------|-------------|
| Batch conversion presets / saved configurations | Phase 2 |
| Cloud sync of converted files | Phase 2 |
| Markdown preview inside the Converter window | Out of scope |
| Drag-and-drop from Mail or Safari directly | Out of scope |
| Auto-update mechanism | "Update available" notification only — no in-app updater |
| Digital signature features | Separate product (MarkSign Platform) |
| OCR of scanned PDFs (image-only PDFs) | Not supported in v1; deferred |
| DOC format (legacy Word) | Supported via hidden engine entry; not advertised in UI |
| Windows / Linux builds | macOS only |
| Gumroad or payment infrastructure | Prepared (Gumroad link from landing page); not required for alpha |

---

## 5. Personas

### Primary — The Knowledge Worker / Researcher

**Profile:** Academic researcher, writer, consultant, or analyst. Accustomed to Finder and Dock. Not a command-line user. Encounters documents in Downloads, email attachments, and cloud syncs.

**Usage pattern:** Both occasional (a few files at a time) and batch (20+ files in one session, e.g., a research project arriving as a zip of PDFs).

**Goal:** Get a clean Markdown version of a document so they can paste it into Obsidian, feed it to an AI tool, or include it in a project.

**Pain point:** Every conversion option today is either cloud-only (privacy risk), too technical (command line), or too expensive (subscription). They want it to work like Preview or QuickLook — native, instant, no friction.

**Key behaviour:** Discovers MarkSign via Finder right-click, not by seeking an app. The entry point is the file, not the app.

---

### Secondary — The Developer / Technical Writer

**Profile:** Software engineer, technical writer, or DevOps practitioner building AI-powered workflows. Comfortable with the Terminal but prefers GUI for repetitive file operations.

**Usage pattern:** Converting documentation files (client specs, API PDFs, onboarding decks) so that AI tools (Claude, Cursor, GitHub Copilot) can read them natively in a repo.

**Goal:** Add `convert to Markdown` as a step in a lightweight ingestion workflow — drag files into MarkSign, get `.md` files out, commit them to a repository.

**Pain point:** Existing Python scripts for conversion are brittle and depend on a configured environment. They want an app they can hand to a non-technical teammate.

**Shapes v1 flows:** The secondary persona confirms that the output file must be in the same folder as the source (so it lands in the right place in the repo) and that batch conversion (20+ files) is a first-class requirement, not an edge case.

---

## 6. Functional Requirements

### 6.1 App shell

| ID | Requirement | User Story | Priority |
|----|-------------|------------|----------|
| FR-01 | The app shall run as a menu bar utility with no Dock icon while idle (`LSUIElement = YES`). | As a user, I want MarkSign to stay out of my way when I'm not converting files. | Must |
| FR-02 | The app shall display a menu bar icon. WHEN the user clicks the icon, the app shall show the Converter window. | As a user, I want to open MarkSign by clicking its icon in the menu bar. | Must |
| FR-03 | The app shall register a URL scheme (`marksign://convert?path=...`). WHEN the URL scheme is invoked, the app shall open the Converter window with the specified file pre-loaded. | As a user who right-clicks a file in Finder, I want MarkSign to open with that file already loaded. | Must |
| FR-04 | The app shall support launch at login via Login Items (macOS System Settings). | As a user who converts files regularly, I want MarkSign running when my Mac starts. | Should |

### 6.2 Converter window — 4 states

#### State 1: Empty

| ID | Requirement | User Story | Priority |
|----|-------------|------------|----------|
| FR-05 | The empty state shall display a document icon, a "Drop files to convert" heading, a "Select Files…" button, and format chips for all supported types. | As a user opening MarkSign for the first time, I want to understand immediately what formats it accepts. | Must |
| FR-06 | The app shall accept files dropped onto the window. WHEN the user drops one or more supported files, the app shall transition to the Files Loaded state. | As a user, I want to drag files from Finder directly into the window. | Must |
| FR-07 | The "Select Files…" button shall open a file picker filtered to supported formats. | As a user, I want to browse for files if I don't want to drag. | Must |
| FR-08 | IF a user drops an unsupported file type, THEN the app shall display an inline error identifying the file and stating the supported formats. | As a user who dropped an unsupported file, I want to know immediately why it was rejected. | Must |

#### State 2: Files Loaded

| ID | Requirement | User Story | Priority |
|----|-------------|------------|----------|
| FR-09 | The files loaded state shall display a scrollable list of queued files. Each row shall show: filename, file size, and destination path ("Save to: [3-level path] ›"). | As a user reviewing my queue, I want to confirm where each file will be saved. | Must |
| FR-10 | The destination path shall be clickable per file. WHEN clicked, it shall open the destination folder in Finder. | As a user, I want to navigate to the destination folder before converting. | Should |
| FR-11 | The toolbar shall display a "+ Add Files" button. The bottom of the list shall display an "Add more files…" strip. Both shall accept additional files. | As a user who wants to add more files to the queue, I want to do so without clearing my current selection. | Must |
| FR-12 | A primary "Convert" button (accent color, 32px) shall be visible and enabled when the queue contains at least one file. WHEN clicked, the app shall transition to the Converting state. | As a user, I want a single prominent button to start conversion. | Must |

#### State 3: Converting

| ID | Requirement | User Story | Priority |
|----|-------------|------------|----------|
| FR-13 | WHILE conversion is in progress, the app shall display per-file status in the list: ✓ Converted, Converting (with spinner), or Waiting. | As a user watching a batch convert, I want to see which files are done and which are in progress. | Must |
| FR-14 | WHILE conversion is in progress, the app shall display a progress bar (accent color fill), a "Converting N of M…" label, and a percentage. | As a user, I want to know how much of the batch is complete. | Must |
| FR-15 | The conversion engine shall attempt formats in priority order per `marksign_engine.py` CONVERTER_CHAIN. IF all engines fail for a file, THEN that file's status shall be marked as "Error" in systemRed. | As a user, I want conversion to try multiple methods before giving up. | Must |

#### State 4: Done

| ID | Requirement | User Story | Priority |
|----|-------------|------------|----------|
| FR-16 | The done state shall display, for each successfully converted file: filename, file size, and an "Open in Finder" link at the sub-row position. | As a user, I want to navigate directly to each converted file. | Must |
| FR-17 | For each file with status "Error": the status column shall show "Error" in systemRed; the sub-row shall show "Open in Finder" to navigate to the source location. The error detail row shall be auto-expanded, showing a title and a body message. No action buttons appear inside the error row. | As a user whose file failed to convert, I want to understand what went wrong and where to find my original file. | Must |
| FR-18 | IF all files converted successfully, THEN the app shall display a success banner with the count of converted files. | As a user, I want confirmation that my batch completed successfully. | Must |
| FR-19 | IF one or more files failed, THEN the app shall display a warning banner. The banner text shall read: "Use 'Open in Finder' on the error file to fix it, then convert again." | As a user with errors, I want actionable guidance — not a generic failure message. | Must |
| FR-20 | A "Clear" button shall be displayed in the done state. WHEN clicked, the app shall reset to the empty state. No "Done" button and no "Convert More Files" button shall appear. | As a user who is finished, I want one clear action to reset. | Must |

### 6.3 Finder integration

| ID | Requirement | User Story | Priority |
|----|-------------|------------|----------|
| FR-21 | The app shall register a Finder right-click context menu item: "Convert with MarkSign". This item shall appear at the top level of the context menu (same level as "Open With", "Share"), not inside the "Quick Actions" submenu. | As a user who encounters a file in Finder, I want to convert it in one right-click without navigating submenus. | Must |
| FR-22 | WHEN the user selects "Convert with MarkSign" in Finder, the app shall open (or foreground if already running) the Converter window with the selected file pre-loaded in the queue. | As a user, I want Finder integration to open the app ready to convert — not perform a silent background conversion. | Must |
| FR-23 | The Finder integration shall be implemented as an Automator service that passes the selected file path to the running app instance via the `marksign://convert?path=...` URL scheme. | Implementation constraint agreed in PRD interview Round 3. | Must |

### 6.4 First run and onboarding

| ID | Requirement | User Story | Priority |
|----|-------------|------------|----------|
| FR-24 | On first launch, IF docling is not installed, THEN the app shall display a "Setting up conversion engine…" screen with a progress indicator and download the docling model silently in the background. | As a first-time user, I want setup to happen automatically without manual steps. | Must |
| FR-25 | After docling is installed, the app shall transition automatically to the empty state. No restart required. | As a user, I don't want to restart the app after setup completes. | Must |
| FR-26 | On first launch, the app shall display a prompt: "Register MarkSign Reader as your default Markdown viewer? [Yes / Not now]" | As a user, I want to opt in to MarkSign Reader as my default .md viewer without it being forced on me. | Must |
| FR-27 | WHERE the user declines the default viewer prompt, the app shall make the same option available in Preferences → "Set as default Markdown viewer". | As a user who said "Not now", I want to be able to change my mind later. | Should |

### 6.5 Supported formats and output

| ID | Requirement | User Story | Priority |
|----|-------------|------------|----------|
| FR-28 | The app shall convert the following formats: PDF, DOCX, PPTX, EPUB, XLSX, TXT, RTF. | As a user, I expect the formats shown in the UI to work. | Must |
| FR-29 | The app shall convert .doc files using the hidden engine entry (libreoffice → pandoc → markitdown). The .doc format shall not appear in the UI format chips. | Hidden support for legacy format. | Should |
| FR-30 | The output file shall be saved to the same folder as the source file by default. The output filename shall be: `[source-filename].md`. | As a user, I want my converted file to appear next to the original without any configuration. | Must |
| FR-31 | The conversion pipeline shall follow CONVERTER_CHAIN priority order per `marksign_engine.py`. IF a primary engine fails, THEN the next engine in the chain shall be attempted before the file is marked as an error. | As a user, I want the app to try multiple methods before telling me it failed. | Must |

### 6.6 MarkSign Reader (companion app)

| ID | Requirement | User Story | Priority |
|----|-------------|------------|----------|
| FR-32 | MarkSign Reader shall be included in the same DMG as the Converter. Both apps shall install together. | As a user installing MarkSign, I want the reader to be available immediately — no second download. | Must |
| FR-33 | MarkSign Reader shall render Markdown files with Newsprint-style CSS (Typora Newsprint aesthetic). | As a user, I want converted Markdown to look like a readable document, not raw text. | Must |
| FR-34 | WHEN registered as the default .md handler, MarkSign Reader shall open `.md` files from Finder double-click, from "Open in Finder" links in the Converter, and from other apps that pass file paths. | As a user, I want a consistent reading experience for all my Markdown files. | Should |
| FR-35 | MarkSign Reader shall have a standard Dock presence when active (not a menu bar app). | MarkSign Reader behaves as a standard document-viewing app; the menu-bar-only pattern applies to the Converter only. | Must |

---

## 7. Non-Functional Requirements

| ID | Requirement | Category |
|----|-------------|----------|
| NFR-01 | The base DMG shall be ≤ 300 MB (docling excluded — downloaded on first run). | Package size |
| NFR-02 | PDF conversion using docling shall complete in ≤ 120 seconds for documents ≤ 50 pages on Apple Silicon. | Performance |
| NFR-03 | The app shall run on macOS 13 (Ventura) and later, on both Apple Silicon and Intel (Rosetta 2). | Compatibility |
| NFR-04 | The app shall not require an internet connection after the initial docling download, except to check for update notifications. | Privacy / offline |
| NFR-05 | No document content shall be sent to any external server. All conversion shall occur locally on the user's machine. | Privacy |
| NFR-06 | The UI shall follow macOS HIG dark mode conventions: unified toolbar 52px, NSTableView rows 52px, status bar 28px, system colors as CSS custom properties. | Design |
| NFR-07 | The app shall be unsigned for alpha distribution (testers right-click → Open). Full Apple Developer ID signing + notarization shall be in place before any paid distribution. | Security / distribution |
| NFR-08 | Auto-update shall display a notification "MarkSign [version] is available — download at faberludens.pro/apps/marksign" in the menu bar. No in-app updater. | Update |

---

## 8. Flows and Wireframes

### Primary flow: Finder right-click → Convert

```
1. User encounters file in Finder (Downloads, email attachment, project folder)
2. Right-clicks file → "Convert with MarkSign" (top-level context menu item)
3. MarkSign opens (or foregrounds); Converter window shows file pre-loaded in queue [State 2]
4. User reviews destination path ("Save to: [3-level path] ›") — no change needed (same folder as source)
5. User clicks "Convert" (accent button, 32px)
6. App transitions to Converting state [State 3] — per-file status, progress bar, percentage
7. Conversion completes (10–60 seconds for typical document)
8. App transitions to Done state [State 4] — "Open in Finder" link below filename
9. User clicks "Open in Finder" — Finder opens showing the .md file
10. User drags .md file into notes app / AI tool / repository
```

### Secondary flow: Menu bar → batch

```
1. User clicks MarkSign menu bar icon
2. Converter window opens [State 1 — empty]
3. User drags 20+ files onto window, or clicks "Select Files…"
4. App transitions to Files Loaded state [State 2] — scrollable list, all destinations shown
5. User adds more files via "+ Add Files" button or "Add more files…" strip
6. User clicks "Convert"
7. App converts in order — per-file status updates in real time [State 3]
8. Done state shows results + success or warning banner [State 4]
9. User clicks "Clear" to reset for next batch
```

### Error recovery flow

```
1. Done state shows one or more files with "Error" status (systemRed)
2. Error detail row auto-expanded: title + body message (no action buttons)
3. Warning banner: "Use 'Open in Finder' on the error file to fix it, then convert again"
4. User clicks "Open in Finder" on the error file → navigates to source
5. User fixes the source file (repairs PDF, saves as different format)
6. User clicks "Clear" → returns to empty state
7. User adds the fixed file → converts again
```

### First-run flow

```
1. User opens MarkSign for the first time
2. App shows "Setting up conversion engine…" screen with progress indicator
3. docling downloads silently in background (progress visible)
4. Setup completes → app transitions to empty state
5. Prompt: "Register MarkSign Reader as your default Markdown viewer? [Yes / Not now]"
6. User responds → app ready to use
```

**Wireframes:** HTML prototype complete through v4 at
`Projects/pipeline/faberludenspro-marksign/2026-04-public-app/prototype.html`

---

## 9. Success Metrics

### Alpha (internal testers)

| Metric | Target |
|--------|--------|
| Engine extraction smoke test passes | 100% of CONVERTER_CHAIN formats convert without error on test set |
| PDF conversion fidelity | Headings, lists, and tables preserved on 80%+ of test PDFs |
| Finder right-click integration works | "Convert with MarkSign" appears at top level on ≥ macOS 13 |
| First-run docling download completes without error | 100% success rate on clean macOS installs |
| App launches and reaches empty state | ≤ 3 seconds from click to visible window |

### v1 launch

| Metric | Target |
|--------|--------|
| Alpha tester conversion success rate | ≥ 90% of files converted without error |
| User-reported conversion quality | ≥ 80% of testers rate output as "usable without editing" |
| Support tickets for install/first-run issues | ≤ 5% of installs generate a support contact |
| "Open in Finder" used after conversion | ≥ 60% of sessions (indicates output is being used) |

---

## 10. Dependencies and Risks

### Dependencies

| Dependency | Owner | Risk if delayed |
|------------|-------|-----------------|
| `biblios_brain.py` CONVERTER_CHAIN extraction into `marksign_engine.py` | Gonçalo | Blocks all app development |
| `docling` library: stable, installable via pip on macOS 13+ | Third-party | Conversion quality depends on docling API stability |
| `rumps` library: macOS menu bar Python framework | Third-party | Menu bar UI blocked if API changes |
| `CustomTkinter`: Python GUI library | Third-party | Window UI blocked if incompatible with PyInstaller |
| `PyInstaller`: packaging | Third-party | DMG build blocked if bundling fails |
| Apple Automator + URL scheme: Finder integration | Apple/macOS | Right-click integration blocked on future macOS changes |
| Apple Developer Program (~R$699/yr) | Gonçalo | Paid distribution blocked until enrolled |

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| docling extraction from biblios_brain.py introduces import conflicts or broken chains | High (unknown dependencies) | High — blocks engine | Smoke test before any UI work (A→B hybrid strategy) |
| PyInstaller fails to bundle docling's native libraries | Medium | High — DMG build fails | Research PyInstaller + docling compatibility early; defer bundled docling to first-run download |
| Automator-based Finder integration deprecated or broken on a future macOS | Medium | Medium — right-click broken | Monitor Apple developer notes; fallback to Quick Action if top-level item not possible |
| docling first-run download too large or too slow | Low | Medium — poor first-run UX | Measure download size; show accurate progress; allow background download without blocking the window |
| libreoffice dependency too large for DMG | Low | Low — DOC support is hidden | DOC is hidden support only; remove from DMG if size is a problem |

---

## 11. Roadmap and Phases

### Phase 0 — Engine validation (pre-alpha)

**Goal:** Confirm that `marksign_engine.py` runs correctly in isolation — before any UI work.

- [ ] Extract CONVERTER_CHAIN from `biblios_brain.py` into `marksign_engine.py`
- [ ] CLI smoke test: convert one file of each supported format from the command line
- [ ] Confirm all engines (docling, pymupdf, pandoc, markitdown, libreoffice) are accessible from the extracted engine
- [ ] Document known issues and limitations

**Gate:** Engine converts all supported formats without error on a test set.

---

### Phase 1 — Minimum Converter (alpha)

**Goal:** Build the 4-state UI and ship a working alpha DMG to testers.

- [ ] Build `marksign_app.py` — `rumps` menu bar + `CustomTkinter` window (4 states)
- [ ] Wire engine into UI: queue management, per-file conversion, status updates
- [ ] Implement first-run docling downloader ("Setting up conversion engine…" screen)
- [ ] Implement Finder integration: Automator service → `marksign://convert?path=...` URL scheme
- [ ] PyInstaller build: generate unsigned alpha DMG
- [ ] Internal testing: all 4 states, all formats, Finder right-click

**Gate:** Alpha DMG installs and converts all supported formats on a clean macOS install.

---

### Phase 2 — Iteration and hardening

**Goal:** Incorporate alpha feedback; harden conversion quality and error handling.

- [ ] Fix all conversion errors surfaced in alpha testing
- [ ] Improve error messages with specific, actionable guidance per failure type
- [ ] Test on Intel Macs via Rosetta 2
- [ ] Performance profiling: ensure ≤ 120 seconds for typical PDFs
- [ ] Update notification: "MarkSign [version] is available" in menu bar

---

### Phase 3 — Companion viewer + v1 DMG

**Goal:** Add MarkSign Reader; build the signed, distributable v1 DMG.

- [ ] Build MarkSign Reader: CustomTkinter window, Newsprint-style CSS Markdown renderer
- [ ] .md file handler registration: first-run opt-in prompt + Preferences option
- [ ] Both apps in single DMG — combined installer
- [ ] Apple Developer ID signing + notarization
- [ ] Landing page: `faberludens.pro/apps/marksign` (Cloudflare Pages)
- [ ] GitHub Releases: versioned DMG hosting
- [ ] Gumroad checkout link on landing page (for paid launch)

**Gate:** Notarized DMG installs on a clean macOS machine; Reader opens .md files; Converter passes all acceptance criteria.

---

### Phase 4 — Post-v1 (Phase 2 features)

- Batch presets / saved conversion configurations
- Cloud sync of output files
- Freemium model activation (trial limits, one-time unlock)

---

## 12. Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| OQ-01 | Can the Automator service reliably place "Convert with MarkSign" at the top level of the Finder context menu (not inside Quick Actions), and does this behaviour persist across macOS major versions? | Gonçalo | Open — validate in Phase 1 |
| OQ-02 | What is the minimum docling model required for acceptable PDF conversion quality, and what is its download size? | Gonçalo | Open — measure in Phase 0 |
| OQ-03 | Does PyInstaller 6.x support bundling docling's native C extensions on both Apple Silicon and Intel? | Gonçalo | Open — validate in Phase 1 |
| OQ-04 | What is the MarkSign Reader rendering strategy? CustomTkinter has no native HTML/CSS renderer — will this require a WebKit webview or a pure Python Markdown-to-Tk renderer? | Gonçalo | Open — evaluate before Phase 3 |
| OQ-05 | Is a freemium model (trial file limit) implemented at the app layer or the engine layer? What is the trial limit? | Gonçalo | Deferred to post-alpha |
| OQ-06 | Should DOC (legacy Word) be advertised in the UI after validation? It is currently hidden support only. | Gonçalo | Deferred to after Phase 0 smoke test confirms reliability |
