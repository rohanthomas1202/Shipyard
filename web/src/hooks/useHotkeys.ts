import { useEffect } from 'react'

type Modifier = 'ctrl' | 'meta' | 'shift' | 'alt'

interface HotkeyConfig {
  key: string
  modifiers?: Modifier[]
  handler: (e: KeyboardEvent) => void
  enabled?: boolean
}

export function useHotkeys(hotkeys: HotkeyConfig[]) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      for (const hotkey of hotkeys) {
        if (hotkey.enabled === false) continue

        const keyMatch = e.key.toLowerCase() === hotkey.key.toLowerCase()
        if (!keyMatch) continue

        const mods = hotkey.modifiers || []
        const ctrlOrMeta = mods.includes('ctrl') || mods.includes('meta')
        const needsShift = mods.includes('shift') ? e.shiftKey : !e.shiftKey
        const needsAlt = mods.includes('alt') ? e.altKey : !e.altKey

        // For ctrl/meta shortcuts, either ctrl or meta satisfies
        if (ctrlOrMeta && !(e.ctrlKey || e.metaKey)) continue
        if (!ctrlOrMeta && (e.ctrlKey || e.metaKey)) continue
        if (!needsShift || !needsAlt) continue

        e.preventDefault()
        hotkey.handler(e)
        return
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [hotkeys])
}
