import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate, useOutletContext, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, LogOut, Menu, MessageSquare, PenLine, Plus, Settings, X } from "lucide-react";
import { useAuth } from "@/lib/AuthContext";
import { logout as logoutRequest } from "@/api/auth";
import { deleteConversation, listConversations, startConversation } from "@/api/writing";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AgentWorkspaceResponse } from "@/api/schemas";

// "Chat" leads (Persistent Brain Decision 3: conversation is the primary way to enter the
// Agent Workspace). Memory and Drafts are deliberately not here - both work invisibly in the
// background (memory quietly informs replies; a document-drafting-with-review workflow was
// removed entirely) and were confusing as standalone nav destinations. Writing Style stays -
// it's a real upload feature you might revisit, same as Research Documents.
const navItems = [
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/documents", label: "Research Documents", icon: FileText },
  { to: "/style-profile", label: "Writing Style", icon: PenLine },
];

// A single persistent left sidebar for the whole app (ChatGPT/Claude-style): app nav, a
// "New chat" action, and the recent-conversations list all live here, always visible - not
// just on the Chat page. Non-chat pages get a centered, padded content column; Chat gets the
// full remaining height/width for its own message-thread layout.
export function AppShell() {
  const { setToken } = useAuth();
  // react-router's Outlet context does not automatically propagate through a nested layout
  // route's own Outlet - each Outlet only carries the context explicitly passed to it, so this
  // layout route (rendered by WorkspaceGate's Outlet) must read the workspace and re-pass it to
  // its own Outlet, or every page nested under it (DocumentsPage, StyleProfilePage, etc.) sees
  // `undefined` from useOutletContext(). Found via a real Playwright browser run.
  const workspace = useOutletContext<AgentWorkspaceResponse>();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isChatRoute = location.pathname.startsWith("/chat");
  const { conversationId: activeConversationId } = useParams<{ conversationId: string }>();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // A route change (tapping a nav item, a conversation, or "New chat") means the user is done
  // with the sidebar on mobile - closing it automatically is what makes a phone/tablet sidebar
  // feel like a menu rather than a permanently obstructing panel. Desktop ignores this state
  // entirely (see the `lg:translate-x-0` class below), so this has no effect there.
  useEffect(() => {
    setIsSidebarOpen(false);
  }, [location.pathname]);

  const conversationsQuery = useQuery({ queryKey: ["conversations"], queryFn: listConversations });

  const newChatMutation = useMutation({
    mutationFn: () => startConversation(),
    onSuccess: (conversation) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      navigate(`/chat/${conversation.conversation_id}`);
    },
  });

  const deleteChatMutation = useMutation({
    mutationFn: (conversationId: number) => deleteConversation(conversationId),
    onSuccess: (_data, conversationId) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      if (String(conversationId) === activeConversationId) navigate("/chat");
    },
  });

  async function handleLogout() {
    try {
      await logoutRequest();
    } finally {
      setToken(null);
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      {/* Mobile-only top bar: the sidebar has no room to stay permanently visible on a phone-
          width screen, so it becomes a slide-in drawer, opened from here. Hidden entirely on
          desktop (lg:hidden), where the sidebar is already always visible. */}
      <div className="flex items-center gap-2 border-b border-sidebar-border bg-sidebar p-3 text-sidebar-foreground lg:hidden fixed inset-x-0 top-0 z-30">
        <Button
          variant="ghost"
          size="sm"
          aria-label="Open menu"
          onClick={() => setIsSidebarOpen(true)}
          className="text-sidebar-foreground"
        >
          <Menu className="size-5" />
        </Button>
        <span className="text-sm font-semibold">ScholarOS</span>
      </div>

      {/* Backdrop: only rendered (and only intercepts taps) while the drawer is open on
          mobile - lg:hidden means it can never appear on desktop even if state is stale. */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 shrink-0 -translate-x-full flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-transform duration-200 ease-in-out",
          "lg:static lg:translate-x-0",
          isSidebarOpen && "translate-x-0",
        )}
      >
        <div className="flex items-center justify-between p-3 lg:block">
          <span className="block px-2 py-1 text-sm font-semibold">ScholarOS</span>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Close menu"
            onClick={() => setIsSidebarOpen(false)}
            className="text-sidebar-foreground lg:hidden"
          >
            <X className="size-5" />
          </Button>
        </div>
        <div className="px-3 pb-3">
          <Button
            className="w-full justify-start gap-2"
            variant="secondary"
            onClick={() => newChatMutation.mutate()}
            disabled={newChatMutation.isPending}
          >
            <Plus className="size-4" />
            New chat
          </Button>
        </div>

        <nav className="space-y-0.5 px-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
                  isActive
                    ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                )
              }
            >
              <item.icon className="size-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-4 flex-1 overflow-y-auto px-2">
          <p className="px-2 pb-1 text-xs font-medium text-sidebar-foreground/60">Recent chats</p>
          {conversationsQuery.data && conversationsQuery.data.length === 0 && (
            <p className="px-2 py-1 text-xs text-sidebar-foreground/50">No conversations yet.</p>
          )}
          {conversationsQuery.data
            ?.slice()
            .reverse()
            .map((conversation) => (
              <div key={conversation.conversation_id} className="group relative">
                <NavLink
                  to={`/chat/${conversation.conversation_id}`}
                  className={({ isActive }) =>
                    cn(
                      "block truncate rounded-md py-1.5 pr-7 pl-2 text-sm",
                      isActive
                        ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                        : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                    )
                  }
                >
                  {conversation.title ?? "Untitled conversation"}
                </NavLink>
                <button
                  type="button"
                  aria-label="Delete conversation"
                  disabled={deleteChatMutation.isPending}
                  onClick={(event) => {
                    event.preventDefault();
                    if (window.confirm("Delete this conversation? This cannot be undone.")) {
                      deleteChatMutation.mutate(conversation.conversation_id);
                    }
                  }}
                  // Hover-to-reveal has no equivalent on touch - a lg:opacity-0 button would be
                  // permanently invisible and untappable on a phone, since there's no hover
                  // state to trigger it. Always visible below the lg breakpoint instead.
                  className="absolute top-1/2 right-1 -translate-y-1/2 rounded p-1 text-sidebar-foreground/50 opacity-100 hover:bg-sidebar-accent hover:text-destructive lg:opacity-0 lg:group-hover:opacity-100"
                >
                  <X className="size-3.5" />
                </button>
              </div>
            ))}
        </div>

        <div className="border-t border-sidebar-border p-2">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
                isActive
                  ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
              )
            }
          >
            <Settings className="size-4" />
            Settings
          </NavLink>
          <div className="mt-1 flex items-center justify-between">
            <ThemeToggle />
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="gap-2 text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            >
              <LogOut className="size-4" />
              Log out
            </Button>
          </div>
        </div>
      </aside>

      {/* pt-14 clears the fixed mobile top bar (only rendered below lg) - lg:pt-0 removes it
          again once that bar is gone and the sidebar is static instead of fixed/overlaid. */}
      <main className="flex flex-1 flex-col overflow-hidden pt-14 lg:pt-0">
        {isChatRoute ? (
          <Outlet context={workspace} />
        ) : (
          <div className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
              <Outlet context={workspace} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
