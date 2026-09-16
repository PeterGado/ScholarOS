import { NavLink, Outlet, useOutletContext } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import { logout as logoutRequest } from "@/api/auth";
import type { AgentWorkspaceResponse } from "@/api/schemas";

const navItems = [
  { to: "/documents", label: "Research Documents" },
  { to: "/style-profile", label: "Writing Style" },
  { to: "/drafts", label: "Drafts" },
];

export function AppShell() {
  const { setToken } = useAuth();
  // react-router's Outlet context does not automatically propagate through a nested layout
  // route's own Outlet - each Outlet only carries the context explicitly passed to it, so this
  // layout route (rendered by WorkspaceGate's Outlet) must read the workspace and re-pass it to
  // its own Outlet, or every page nested under it (DocumentsPage, DraftsPage, etc.) sees
  // `undefined` from useOutletContext(). Found via a real Playwright browser run.
  const workspace = useOutletContext<AgentWorkspaceResponse>();

  async function handleLogout() {
    try {
      await logoutRequest();
    } finally {
      setToken(null);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <span className="font-semibold">ScholarOS</span>
          <nav className="flex gap-4 text-sm">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  isActive ? "font-medium text-foreground" : "text-muted-foreground hover:text-foreground"
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <button
            onClick={handleLogout}
            className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
          >
            Log out
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet context={workspace} />
      </main>
    </div>
  );
}
