import * as React from "react"
import { cn } from "cn"

// Replaces plain "Loading..." text with a block shaped like the eventual content - used by
// ChatDetailPage, DocumentsPage, SegmentsPage instead of each rolling its own loading string.
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-lg bg-muted", className)}
      {...props}
    />
  )
}

export { Skeleton }
