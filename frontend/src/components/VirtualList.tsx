import { useImperativeHandle, useRef, type ReactNode, type Ref } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { cn } from "@/lib/utils";

/** No padding is applied to the scroll container itself: a scroll element's own padding is not
 * part of the coordinate space `translateY` positions rows in, so it would desync every row.
 * Callers pad the wrapper around the list, or the row content, instead. */
export interface VirtualListProps<T> {
  items: readonly T[];
  getItemKey: (item: T, index: number) => string | number;
  renderItem: (item: T, index: number) => ReactNode;
  /** Height used for a row before it has been measured, as a number or per-row function -
   * rows are measured for real once rendered, this only sets scroll geometry for the rest. */
  estimateSize: number | ((item: T, index: number) => number);
  overscan?: number;
  gap?: number;
  /** "end" keeps the viewport pinned to the bottom when rows are added or measured - the
   * chat thread's own "stay at the newest message" behavior, which would otherwise drift as
   * row estimates are replaced by real heights. */
  anchorTo?: "start" | "end";
  className?: string;
  ariaLabel?: string;
  ref?: Ref<VirtualListHandle>;
}

/** A row plus where it sat relative to the viewport, recorded before the list's contents change
 * so the same row can be put back in the same place afterwards. */
export interface VirtualListScrollAnchor {
  key: string | number;
  /** Pixels between the row's top and the top of the visible area (normally <= 0). */
  offset: number;
}

export interface VirtualListHandle {
  /** Scrolls to the bottom of the list, following rows that are measured (and so change the
   * total height) while the scroll is in flight - a plain `scrollTop = scrollHeight` lands short
   * whenever a row turns out taller than its estimate. */
  scrollToEnd: (behavior?: ScrollBehavior) => void;
  /** The topmost rendered row and its position on screen, for restoring the reading position
   * after rows are prepended above it (the chat page's "load older messages"). */
  captureAnchor: () => VirtualListScrollAnchor | null;
  restoreAnchor: (anchor: VirtualListScrollAnchor) => void;
}

/**
 * Renders only the rows near the viewport of its own scroll container, using
 * `@tanstack/react-virtual` - the same ecosystem as the `@tanstack/react-query` these pages
 * already use, and the one library that handles variable row heights (markdown replies can be
 * one line or forty) by measuring each rendered row instead of assuming a fixed size.
 *
 * The container is `overflow-y-auto` with whatever max height the caller's className sets; a
 * list shorter than that height simply renders every row and never grows a scrollbar, so callers
 * can cap a long list without changing how a short one looks.
 *
 * Rows are role="listitem" inside role="list" (not ul/li) because the virtualizer needs a plain
 * spacer element between the scroller and the rows, which is not valid inside a ul.
 */
export function VirtualList<T>({
  items,
  getItemKey,
  renderItem,
  estimateSize,
  overscan = 4,
  gap = 0,
  anchorTo,
  className,
  ariaLabel,
  ref,
}: VirtualListProps<T>) {
  const listRef = useRef<HTMLDivElement | null>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => listRef.current,
    estimateSize: (index) =>
      typeof estimateSize === "function" ? estimateSize(items[index], index) : estimateSize,
    getItemKey: (index) => getItemKey(items[index], index),
    overscan,
    gap,
    anchorTo,
  });

  useImperativeHandle(
    ref,
    () => ({
      scrollToEnd: (behavior = "auto") => virtualizer.scrollToEnd({ behavior }),
      captureAnchor: () => {
        const scrollTop = listRef.current?.scrollTop ?? 0;
        let anchor: { key: string | number; offset: number } | null = null;
        // The row currently crossing the top of the viewport, not simply the first rendered one
        // (overscan rows sit above the viewport and are rendered too).
        for (const row of virtualizer.getVirtualItems()) {
          if (row.start > scrollTop) break;
          anchor = {
            key: typeof row.key === "bigint" ? row.key.toString() : row.key,
            offset: row.start - scrollTop,
          };
        }
        return anchor;
      },
      restoreAnchor: (anchor) => {
        const row = virtualizer.measurementsCache.find((measurement) => measurement.key === anchor.key);
        if (!row || !listRef.current) return;
        // anchor.offset = originalRow.start - originalScrollTop.
        // After prepending new rows above, the row's start has shifted down.
        // To restore the same viewport position: newScrollTop = newRow.start - anchor.offset.
        listRef.current.scrollTop = row.start - anchor.offset;
      },
    }),
    [virtualizer],
  );

  return (
    <div
      ref={listRef}
      role="list"
      aria-label={ariaLabel}
      className={cn("relative overflow-y-auto", className)}
    >
      <div
        role="presentation"
        style={{ position: "relative", width: "100%", height: virtualizer.getTotalSize() }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => (
          <div
            key={virtualRow.key}
            role="listitem"
            data-index={virtualRow.index}
            ref={virtualizer.measureElement}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              transform: `translateY(${virtualRow.start}px)`,
            }}
          >
            {renderItem(items[virtualRow.index], virtualRow.index)}
          </div>
        ))}
      </div>
    </div>
  );
}
