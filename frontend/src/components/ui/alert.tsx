import * as React from "react"
import { cn } from "cn"

// Centralizes the destructive-box pattern (box + message + optional retry action) that was
// duplicated three times in ChatDetailPage.tsx - same visual shape as before, now under one
// component and the new color tokens instead of three copy-pasted divs.
function Alert({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert"
      role="alert"
      className={cn(
        "mx-auto max-w-2xl rounded-xl border border-destructive/50 bg-destructive/5 px-4 py-3",
        className
      )}
      {...props}
    />
  )
}

function AlertTitle({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="alert-title"
      className={cn("mb-1 text-sm font-medium text-destructive", className)}
      {...props}
    />
  )
}

function AlertDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="alert-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

export { Alert, AlertTitle, AlertDescription }
