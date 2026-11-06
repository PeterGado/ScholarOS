import { MoonIcon, SunIcon } from "@phosphor-icons/react";
import { useTheme } from "@/lib/ThemeContext";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      aria-label={
        theme === "dark" ? "Switch to light theme" : "Switch to dark theme"
      }
      // Vibrant theme-fitting colors:
      // - Light mode: primary navy background hover (subtle 10%/5% opacity)
      // - Dark mode: sidebar accent background at 30%/50% opacity
      // - Text: sidebar foreground adapts to theme for contrast
      // - Smooth transition + focus-visible ring for accessibility
      className="
        group-hover:bg-primary/10 hover:bg-primary/5
        dark:bg-sidebar-accent/30 dark:hover:bg-sidebar-accent/50
        text-sidebar-foreground transition-colors duration-200
        focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2
        aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20
      "
    >
      {theme === "dark" ? (
        <SunIcon
          className="size-4 text-sidebar-foreground transition-colors duration-200"
        />
      ) : (
        <MoonIcon
          className="size-4 text-sidebar-foreground transition-colors duration-200"
        />
      )}
    </Button>
  );
}
