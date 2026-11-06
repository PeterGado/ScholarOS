import { MoonIcon, SunIcon } from "@phosphor-icons/react";
import { useTheme } from "@/lib/ThemeContext";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <Button
      size="icon"
      onClick={toggleTheme}
      aria-label={
        theme === "dark" ? "Switch to light theme" : "Switch to dark theme"
      }
      // Solid blue instead of a transparent ghost button. The toggle is rendered both on the
      // ivory landing-page header and on the navy sidebar, and a transparent button with
      // `text-sidebar-foreground` (white in the light theme) was invisible against the ivory
      // page - only the hover state ever showed. A filled button is visible at rest in both
      // placements regardless of what sits behind it.
      //
      // `bg-primary-hover` (#1E3A8A light / #5578E8 dark) is a step brighter than `bg-primary`,
      // so the button stays distinguishable from the light-mode sidebar, which is itself
      // `--sidebar: #172554` backed by the same navy as `--primary`. The white inner border
      // gives it an edge on that navy; on the ivory page it reads as a plain blue button.
      // Brightening on hover (rather than swapping to `--primary`) avoids landing back on the
      // sidebar's own color mid-interaction.
      className="
        border-white/25 bg-primary-hover text-primary-foreground shadow-sm
        hover:brightness-110
        transition-all duration-200
        focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2
      "
    >
      {theme === "dark" ? (
        <SunIcon className="size-4" />
      ) : (
        <MoonIcon className="size-4" />
      )}
    </Button>
  );
}
