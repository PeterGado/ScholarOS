import { MoonIcon, SunIcon } from "@phosphor-icons/react";
import { useTheme } from "@/lib/ThemeContext";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <Button
      // Explicit default variant: the same fill as the header's "Get started" button
      // (bg-primary #172554, hover:bg-primary-hover #1E3A8A), so the two read as one
      // control family rather than two different blues.
      //
      // A filled variant rather than ghost: the toggle also renders on the ivory
      // landing-page header, where a transparent button with a white icon was invisible
      // at rest. The inner white border keeps an edge on the navy sidebar, whose
      // background (--sidebar #172554) is the same navy as --primary.
      variant="default"
      size="icon"
      onClick={toggleTheme}
      aria-label={
        theme === "dark" ? "Switch to light theme" : "Switch to dark theme"
      }
      className="
        border-white/25 shadow-sm
        transition-colors duration-200
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
