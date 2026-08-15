import { useState, type CSSProperties } from "react"

import type { GalleryPreset } from "@/lib/types"

export function GameLogo({ game, className = "" }: { game: GalleryPreset; className?: string }) {
  const [imageFailed, setImageFailed] = useState(false)

  return <span className={`game-logo ${className}`.trim()} style={{ "--game-accent": game.accent } as CSSProperties} aria-hidden="true">
    {game.logoUrl && !imageFailed ? <img src={game.logoUrl} alt="" onError={() => setImageFailed(true)} /> : <b>{game.shortName.slice(0, 2)}</b>}
  </span>
}
