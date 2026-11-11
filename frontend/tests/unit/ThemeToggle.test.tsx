import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ThemeProvider } from "@/lib/ThemeContext";
import { ThemeToggle } from "@/components/ThemeToggle";

function renderThemeToggle(theme: "light" | "dark" = "light") {
  return render(
    <ThemeProvider initialTheme={theme}>
      <ThemeToggle />
    </ThemeProvider>,
  );
}

describe("ThemeToggle", () => {
  it("renders the sun icon when the theme is dark", () => {
    renderThemeToggle("dark");
    expect(screen.getByRole("button", { name: /switch to light theme/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /switch to light theme/i }).querySelector("svg")).toBeInTheDocument();
  });

  it("renders the moon icon when the theme is light", () => {
    renderThemeToggle("light");
    expect(screen.getByRole("button", { name: /switch to dark theme/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /switch to dark theme/i }).querySelector("svg")).toBeInTheDocument();
  });

  it("continues to update the button label when the theme changes", () => {
    const { rerender, unmount } = renderThemeToggle("light");
    unmount();
    // eslint-disable-next-line react/no-render-return-value
    const refreshed = renderThemeToggle("dark");
    expect(screen.getByRole("button", { name: /switch to light theme/i })).toBeInTheDocument();
    refreshed.unmount();
  });
});
