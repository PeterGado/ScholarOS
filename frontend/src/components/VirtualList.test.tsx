import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";
import { VirtualList, type VirtualListHandle } from "./VirtualList";

// jsdom performs no layout: every element reports 0 for client/offset sizes, which would make
// the virtualizer think the viewport and every row are zero pixels tall. These stubs give it a
// real 300px viewport and rows that match their 100px estimate, so the window it renders is a
// deterministic, checkable subset instead of "whatever fits in nothing".
const VIEWPORT_HEIGHT = 300;
const ROW_HEIGHT = 100;

const items = Array.from({ length: 100 }, (_, index) => ({ id: index, label: `Item ${index}` }));

let offsetHeightDescriptor: PropertyDescriptor | undefined;

function renderList(
  rows = items,
  props: Partial<ComponentProps<typeof VirtualList<(typeof items)[number]>>> = {},
) {
  return render(
    <VirtualList
      items={rows}
      getItemKey={(item) => item.id}
      estimateSize={ROW_HEIGHT}
      renderItem={(item) => <p>{item.label}</p>}
      ariaLabel="Test rows"
      {...props}
    />,
  );
}

describe("VirtualList", () => {
  beforeEach(() => {
    vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(VIEWPORT_HEIGHT);
    // The virtualizer measures each rendered row through offsetHeight. jsdom reports 0 for it,
    // so rows are standing in at their estimated height, as they would if they had rendered.
    offsetHeightDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "offsetHeight");
    Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
      configurable: true,
      get: () => ROW_HEIGHT,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    if (offsetHeightDescriptor) {
      Object.defineProperty(HTMLElement.prototype, "offsetHeight", offsetHeightDescriptor);
    }
  });

  it("renders only the rows near the viewport of a long list", () => {
    renderList();

    // 300px viewport / 100px rows = the first ~3 rows, plus the small default overscan.
    expect(screen.getByText("Item 0")).toBeInTheDocument();
    expect(screen.getByText("Item 1")).toBeInTheDocument();
    expect(screen.queryByText("Item 50")).not.toBeInTheDocument();
    expect(screen.queryByText("Item 99")).not.toBeInTheDocument();
    expect(screen.getAllByRole("listitem").length).toBeLessThan(items.length);
  });

  it("moves the window as the container scrolls", async () => {
    renderList();
    const list = screen.getByRole("list", { name: "Test rows" });

    // 20 rows down, and the rendered window follows to rows 20-22.
    list.scrollTop = 20 * ROW_HEIGHT;
    fireEvent.scroll(list);

    await waitFor(() => expect(screen.getByText("Item 20")).toBeInTheDocument());
    expect(screen.queryByText("Item 0")).not.toBeInTheDocument();
  });

  it("renders every row when the whole list fits in the container", () => {
    const few = items.slice(0, 3);
    renderList(few);

    for (const item of few) {
      expect(screen.getByText(item.label)).toBeInTheDocument();
    }
    expect(screen.getAllByRole("listitem")).toHaveLength(few.length);
  });

  it("calls renderItem with the row and its index", () => {
    const renderItem = vi.fn((item: (typeof items)[number], index: number) => <p>{`${item.label} at ${index}`}</p>);
    renderList(items.slice(0, 2), { renderItem });

    expect(renderItem).toHaveBeenCalledWith(expect.objectContaining({ id: 0 }), 0);
    expect(screen.getByText("Item 1 at 1")).toBeInTheDocument();
  });

  it("restores the reading position after rows are prepended above the anchor", () => {
    const ref = { current: null as VirtualListHandle | null };
    const { rerender } = render(
      <VirtualList
        ref={ref}
        items={items.slice(30, 40)}
        getItemKey={(item) => item.id}
        estimateSize={ROW_HEIGHT}
        renderItem={(item) => <p>{item.label}</p>}
        ariaLabel="Test rows"
      />,
    );
    const list = screen.getByRole("list", { name: "Test rows" });

    // Scrolled one row down, so row 31 starts exactly at the top of the viewport.
    list.scrollTop = ROW_HEIGHT;
    fireEvent.scroll(list);
    const anchor = ref.current?.captureAnchor();
    expect(anchor).toEqual({ key: 31, offset: 0 });

    // 20 older rows arrive above the anchor; without the restore, scrollTop would stay put and
    // the user's reading position would jump 20 rows down.
    rerender(
      <VirtualList
        ref={ref}
        items={items.slice(10, 40)}
        getItemKey={(item) => item.id}
        estimateSize={ROW_HEIGHT}
        renderItem={(item) => <p>{item.label}</p>}
        ariaLabel="Test rows"
      />,
    );
    ref.current?.restoreAnchor(anchor!);

    expect(list.scrollTop).toBe(21 * ROW_HEIGHT);
  });
});
