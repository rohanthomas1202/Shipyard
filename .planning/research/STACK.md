# Technology Stack: IDE UI Rebuild (v1.1)

**Project:** Shipyard v1.1 IDE UI
**Researched:** 2026-03-27

## Recommended Stack

### Existing (No Changes)

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| React | 19.2.4 | UI framework | Keep |
| Tailwind CSS | 4.2.2 | Styling (glassmorphic design system) | Keep |
| Vite | 8.0.1 | Build/dev server | Keep |
| TypeScript | ~5.9.3 | Type safety | Keep |
| FastAPI | >=0.115.0 | Backend API server | Keep (minor endpoint additions) |

### New Dependencies

| Technology | Version | Purpose | Why This One |
|------------|---------|---------|--------------|
| `react-resizable-panels` | ^4.7 | Resizable three-panel IDE layout | De facto standard (1777 npm dependents), WAI-ARIA compliant, built-in localStorage persistence via `autoSaveId`, ~8KB gzipped |
| `diff` (jsdiff) | ^7.0 | Line-level diff computation for side-by-side view | Most popular JS diff library, Myers O(ND) algorithm, supports line/word/character diffs, ~15KB gzipped |
| `shiki` | ^3.0 | Syntax highlighting for read-only file viewer | VS Code's own TextMate grammar engine, lazy-loads language grammars on demand, accurate highlighting for 200+ languages, ~25KB core |

### Supporting Libraries (Already Present, No Install Needed)

| Library | Purpose in v1.1 |
|---------|-----------------|
| Material Symbols (Google Fonts CDN) | Icons throughout IDE UI (already loaded) |
| CSS custom properties | Glassmorphic design tokens (already defined) |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Panel layout | react-resizable-panels | CSS Grid (current) | No drag-to-resize, no persist, no collapse/expand with animation |
| Panel layout | react-resizable-panels | allotment | Less maintained, fewer npm dependents, react-resizable-panels is the shadcn/ui choice |
| Diff rendering | jsdiff + custom renderer | react-diff-viewer | Brings its own opinionated styling that conflicts with glassmorphic design system; we need full control over diff presentation |
| Diff rendering | jsdiff + custom renderer | Monaco DiffEditor | ~2MB bundle for a feature we can build in ~200 lines with jsdiff |
| Syntax highlighting | Shiki | Prism.js | Prism is older, fewer languages, no VS Code grammar compatibility |
| Syntax highlighting | Shiki | Monaco Editor (read-only) | ~2MB bundle overhead for read-only display is unjustifiable |
| Syntax highlighting | Shiki | highlight.js | Fewer languages, less accurate tokenization than TextMate grammars |
| Code editor | None (read-only view) | Monaco Editor | Users do not edit code in browser -- the agent edits. Read-only display with Shiki is sufficient for v1.1 |

## Installation

```bash
cd web

# New runtime dependencies
npm install react-resizable-panels diff shiki

# Type definitions (diff ships its own types, shiki ships its own types)
# react-resizable-panels ships its own types
# No additional @types/ packages needed
```

## Bundle Impact Assessment

| Library | Gzipped Size | Lazy-Loadable | Impact |
|---------|-------------|---------------|--------|
| react-resizable-panels | ~8KB | No (needed at layout level) | Negligible |
| diff | ~15KB | Yes (only in DiffPanel) | Low |
| shiki (core) | ~25KB | Yes (only in FileViewer/DiffPanel) | Low |
| shiki grammars | ~2-5KB each | Yes (loaded per language on demand) | Negligible per file |
| **Total** | **~48KB** | Partially | **Acceptable** |

Current bundle is lightweight (React 19 + Tailwind 4 only). Adding ~48KB gzipped is well within acceptable limits for an IDE-class application.

## Backend Additions (Python, No New Dependencies)

The backend needs two endpoint additions using only existing dependencies:

```python
# server/main.py additions:

# 1. Extend /browse to include files (currently dirs-only)
# No new dependencies -- just remove the is_dir() filter

# 2. Add GET /files?path= for file content
# No new dependencies -- uses pathlib for reading, mimetypes for language detection
```

## Sources

- [react-resizable-panels npm](https://www.npmjs.com/package/react-resizable-panels) - v4.7.6
- [diff (jsdiff) npm](https://www.npmjs.com/package/diff) - text diffing
- [Shiki](https://shiki.style/) - syntax highlighter
- Existing `web/package.json` audited for current dependencies
