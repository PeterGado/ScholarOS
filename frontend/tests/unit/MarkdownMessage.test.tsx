import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkdownMessage } from "@/components/MarkdownMessage";

describe("MarkdownMessage", () => {
  it("renders plain text unchanged", () => {
    render(<MarkdownMessage content="Hello world" />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("renders a heading as an <h1>", () => {
    render(<MarkdownMessage content="# Heading" />);
    const heading = document.querySelector("h1");
    expect(heading).toBeInTheDocument();
    expect(heading?.textContent).toBe("Heading");
  });

  it("renders inline markdown as formatted text", () => {
    render(<MarkdownMessage content={"**bold** and `code` and *italic*"} />);
    expect(screen.getByText("bold")).toBeInTheDocument();
    expect(screen.getByText("code")).toBeInTheDocument();
    expect(screen.getByText("italic")).toBeInTheDocument();
  });
});
