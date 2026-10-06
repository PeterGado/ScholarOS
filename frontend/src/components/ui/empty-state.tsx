import type { ComponentProps, ReactNode } from "react"
import type { Icon as PhosphorIcon } from "@phosphor-icons/react"
import { cn } from "cn"

// A bounded, deliberate-looking placeholder for a page/section with nothing in it yet -
// replaces a single line of gray text that otherwise leaves a sparse page looking unfinished
// (2026-10-05 UI audit finding). Deliberately a bordered box with generous padding rather than
// full-viewport vertical centering, which would need AppShell's content wrapper restructured
// and risks interacting badly with pages that do have long, scrollable content.
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  ...props
}: ComponentProps<"div"> & {
  icon: PhosphorIcon
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div
      data-slot="empty-state"
      className={cn(
        "flex flex-col items-center gap-3 rounded-xl border border-dashed border-border px-6 py-16 text-center",
        className
      )}
      {...props}
    >
      <div className="flex size-10 items-center justify-center rounded-xl bg-muted">
        <Icon className="size-5 text-muted-foreground" />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="mx-auto max-w-sm text-sm text-muted-foreground">{description}</p>
      </div>
      {action}
    </div>
  )
}
