# Product Marketing Context — MarkSign

## Product Family

MarkSign is a product family with three surfaces:

| Surface | Description | Status |
|---------|-------------|--------|
| **MarkSign Converter** | Native macOS menu bar app — converts PDF/DOCX/PPTX/EPUB/XLSX/TXT/RTF to structured Markdown via local pipeline. Ships with MarkSign Reader. | Active development (alpha) |
| **MarkSign Reader** | Companion Markdown viewer with Newsprint-style CSS. Ships in Converter DMG. Registers as default .md opener (opt-in). | Ships with Converter |
| **MarkSign Platform** | SaaS digital signature for Markdown files — ICP-Brasil/eIDAS, hash + JWT policy + optional encryption. Git-native. | Business plan written, no code |
| **MarkSign Panel** | Chrome extension (MV3, Side Panel API) for converting web pages/PDFs to Markdown in-browser | Phase 1 cleanup done |

**This context focuses primarily on MarkSign Converter** (first to market). Platform marketing will be a separate effort.

## MarkSign Converter

**Name:** MarkSign Converter
**Type:** Native macOS utility app (menu bar, no Dock icon)
**One-liner:** Convert any document to Markdown. Right-click. Done.
**Distribution:** Direct DMG download — landing page + GitHub Releases
**Pricing:** Free alpha → one-time purchase (freemium post-alpha, Gumroad)
**Status:** Engine production-ready; UI built; packaging in progress

## What It Does

A menu bar utility that converts documents to structured Markdown in one action — either via Finder right-click ("Convert with MarkSign") or drag-and-drop into the app window. Entirely local. No cloud upload. No subscription. No command line.

**Supported formats:** PDF, DOCX, PPTX, EPUB, XLSX, TXT, RTF
**Engine:** Multi-pass local pipeline (docling → pymupdf → pandoc → markitdown)
**Output:** Clean .md file saved in the same folder as the source

**Key behaviors:**
- Right-click integration at Finder top level (not buried in Quick Actions submenu)
- Batch conversion (20+ files in one session)
- Menu bar app — no Dock icon unless window is open
- Docling engine downloaded on first run (base DMG ~100MB, not 300MB+)
- Ships with MarkSign Reader in the same DMG

## Target Audience

### Primary — The Knowledge Worker / Researcher

- Academic researchers, writers, consultants, analysts
- Finder-native users (not command-line)
- Encounter documents in Downloads, email attachments, cloud syncs
- Need clean Markdown for Obsidian, Bear, Notion, AI tools (Claude, ChatGPT), or repos
- **Discovery path:** The file is the entry point, not the app. They find MarkSign through Finder right-click.

### Secondary — The Developer / Technical Writer

- Software engineers, technical writers, DevOps
- Converting documentation (client specs, API PDFs, onboarding decks) for AI tool ingestion
- Want an app they can hand to a non-technical teammate
- Batch conversion for repo workflows

### Psychographic Profile

- Privacy-conscious (won't upload sensitive docs to cloud converters)
- Productivity-focused (hate friction, love native OS integration)
- Markdown-native (Obsidian, Bear, VS Code, repos)
- Willing to pay once for a tool that saves repeated pain

## Problem We Solve

Converting documents to Markdown today requires either:
- **Web services** that raise privacy concerns for sensitive documents
- **Command-line tools** with steep setup requirements (Python envs, dependencies)
- **Paid subscriptions** to cloud converters with per-file or per-month billing
- **Manual copy-paste** that destroys structure (headings, tables, lists lost)

There is no native macOS converter that is local, free of recurring cost, privacy-respecting, and integrable with the Finder workflow.

## Positioning & Differentiation

| Dimension | MarkSign | Cloud converters (CloudConvert, Zamzar) | CLI tools (pandoc, docling) | AI extraction (ChatGPT upload) |
|---|---|---|---|---|
| Privacy | 100% local | Cloud upload required | Local | Cloud upload |
| Cost | One-time purchase | Per-file or subscription | Free (setup cost) | Subscription |
| Ease of use | Right-click in Finder | Browser upload flow | Terminal commands | Chat interface |
| Structural fidelity | Multi-engine pipeline | Variable | Good (if configured) | Inconsistent |
| Batch support | Native (20+ files) | Limited/slow | Script required | One at a time |
| macOS integration | Menu bar + Finder | None | None | None |

**Key differentiator:** The only native macOS app that converts documents to Markdown locally with Finder right-click integration — no cloud, no subscription, no terminal.

## Pricing Strategy

| Phase | Model | Price | Notes |
|---|---|---|---|
| Alpha | Free | $0 | Direct download, feedback collection |
| Post-alpha | Freemium | TBD (likely $9–19 one-time) | Free: basic formats; Paid: full suite + batch |
| Platform (future) | SaaS subscription | TBD | Enterprise digital signature |

**Distribution:** Gumroad link from landing page (prepared, not yet active)

## Competitive Landscape

**Direct competitors (document → Markdown):**
- Pandoc (CLI, free, excellent but technical)
- MarkItDown by Microsoft (CLI library, emerging)
- Various web converters (privacy issues, subscription models)

**Adjacent / indirect:**
- PDF Expert, Preview (read PDFs, don't convert to MD)
- Obsidian plugins (limited format support, variable quality)
- AI tools (ChatGPT, Claude file upload — cloud, inconsistent, per-message cost)

**Our moat:** Production-grade multi-engine pipeline (docling + pymupdf + pandoc + markitdown) packaged as a native macOS app with true Finder integration. No competitor combines this engine quality with this UX simplicity.

## Voice & Tone (Marketing)

- **Direct and confident** — the tool does what it says
- **Technical credibility without jargon** — mention the engine but don't require understanding it
- **Understated** — utility tools earn trust through reliability, not hype
- **Privacy-forward** — lead with "100% local" in every touchpoint

**Words we use:** local, private, native, structured, clean, Finder, right-click, drag-and-drop
**Words we avoid:** AI-powered (except for Platform), cloud, upload, subscription, freemium (internally only)

## Key Metrics (to track)

- Landing page → download conversion rate
- Downloads → active users (30-day)
- Files converted per user per week (engagement)
- Format distribution (which formats drive adoption)
- Batch vs. single-file usage ratio
- Free → paid conversion (post-alpha)
- Chrome extension installs (Panel surface)

## Launch Strategy

1. **Alpha (current):** Direct distribution to personal network + Markdown communities. Feedback collection.
2. **Public beta:** Landing page on faberludens.pro + GitHub Releases. Content marketing on Obsidian forums, r/ObsidianMD, Hacker News.
3. **Paid launch:** Gumroad checkout. PR angle: "The privacy-first document converter for your Markdown workflow."
4. **Chrome extension:** CWS listing (pending: icon PNGs, privacy policy, $5 developer account)

## Channels (Likely)

- **Obsidian community** (primary — highest concentration of target users)
- **Hacker News / Product Hunt** (developer/technical writer audience)
- **Reddit** (r/ObsidianMD, r/macapps, r/productivity)
- **GitHub** (open-source-adjacent credibility)
- **Content marketing** ("Why your documents should be Markdown", privacy angle)
- **Word of mouth** (utility tools spread through workflows)

## Technical Stack

- Python + CustomTkinter (app UI)
- PyInstaller (macOS packaging, .app bundle)
- Engine: docling, PyMuPDF, pandoc, markitdown, pdfminer.six
- Distribution: DMG (direct download)
- Landing page: Cloudflare Pages
- Payment (future): Gumroad

## Company Context

**Faber-Ludens Pro** — UX consultancy building own-product revenue. MarkSign Converter is the first utility product. Low-risk (no infrastructure cost, no subscriptions to manage), validates distribution and pricing capability before larger SaaS plays (Dear Biblios, MarkSign Platform).
