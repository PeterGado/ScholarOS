import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Theme = "light" | "dark";

// Keep in sync with the pre-paint inline script in index.html. That script cannot import this
// module (it has to run before the bundle loads), so the key and the media query are
// deliberately duplicated there.
const STORAGE_KEY = "scholaros-theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

/** The user's explicit choice, or null when they have never toggled. */
function readStoredTheme(): Theme | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // localStorage unavailable (private browsing, etc.) - fall through to system preference.
  }
  return null;
}

function systemTheme(): Theme {
  return window.matchMedia?.(DARK_QUERY).matches ? "dark" : "light";
}

function getInitialTheme(): Theme {
  return readStoredTheme() ?? systemTheme();
}

export function ThemeProvider({ children, initialTheme }: { children: ReactNode; initialTheme?: Theme }) {
  const [theme, setTheme] = useState<Theme>(() => initialTheme ?? getInitialTheme());

  // Keep <html> in sync for in-app changes. index.html's inline script already did this before
  // first paint, which is what removed the light-to-dark flash on load.
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  // Follow the OS while no explicit choice exists (2026-11-06). The system preference used to be
  // read once at mount and then frozen: flipping the OS theme mid-session changed nothing until
  // a reload, and the old mount-time write to localStorage *pinned* the system value as though
  // the user had chosen it, so the freeze survived reloads too.
  useEffect(() => {
    const query = window.matchMedia?.(DARK_QUERY);
    if (!query?.addEventListener) return;
    const handleChange = (event: MediaQueryListEvent) => {
      if (readStoredTheme() === null) setTheme(event.matches ? "dark" : "light");
    };
    query.addEventListener("change", handleChange);
    return () => query.removeEventListener("change", handleChange);
  }, []);

  // Only an explicit toggle is persisted. Writing the current value on mount would record the
  // system preference as a user choice and permanently disable the listener above.
  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Best-effort persistence only.
    }
  }

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within a ThemeProvider");
  return context;
}
