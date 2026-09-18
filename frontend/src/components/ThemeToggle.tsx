import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/lib/ThemeContext";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      className="text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
    >
      {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  );
}
