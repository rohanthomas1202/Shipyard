import { createHighlighter, type Highlighter, type BundledLanguage } from 'shiki'

let highlighterPromise: Promise<Highlighter> | null = null

// Extension to Shiki language map
const LANG_MAP: Record<string, BundledLanguage> = {
  py: 'python', ts: 'typescript', tsx: 'tsx', js: 'javascript', jsx: 'jsx',
  rs: 'rust', go: 'go', rb: 'ruby', java: 'java', kt: 'kotlin',
  cs: 'csharp', cpp: 'cpp', c: 'c', h: 'c', hpp: 'cpp',
  md: 'markdown', json: 'json', yaml: 'yaml', yml: 'yaml',
  html: 'html', css: 'css', scss: 'scss', sql: 'sql',
  sh: 'bash', bash: 'bash', zsh: 'bash', fish: 'fish',
  toml: 'toml', xml: 'xml', svg: 'xml', graphql: 'graphql',
  dockerfile: 'dockerfile', makefile: 'makefile',
}

export function mapLanguage(lang: string): BundledLanguage {
  const lower = lang.toLowerCase()
  return (LANG_MAP[lower] as BundledLanguage) || (lower as BundledLanguage)
}

async function getHighlighter(lang: BundledLanguage): Promise<Highlighter> {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: ['vitesse-dark'],
      langs: [lang],
    })
  }
  const hl = await highlighterPromise
  const loaded = hl.getLoadedLanguages()
  if (!loaded.includes(lang)) {
    try { await hl.loadLanguage(lang) } catch { /* fallback to text */ }
  }
  return hl
}

export async function highlightCode(code: string, lang: string): Promise<string> {
  const mappedLang = mapLanguage(lang)
  try {
    const hl = await getHighlighter(mappedLang)
    return hl.codeToHtml(code, { lang: mappedLang, theme: 'vitesse-dark' })
  } catch {
    // Fallback: return escaped plain text
    const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return `<pre style="background:transparent;margin:0"><code>${escaped}</code></pre>`
  }
}
