import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate, useOutletContext, useParams } from "react-router-dom";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChatIcon,
  FileTextIcon,
  GearIcon,
  ListIcon,
  PencilLineIcon,
  PlusIcon,
  SignOutIcon,
  StackIcon,
  XIcon,
} from "@phosphor-icons/react";
import { useAuth } from "@/lib/AuthContext";
import { logout as logoutRequest } from "@/api/auth";
import { deleteConversation, listConversations, startConversation } from "@/api/writing";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/apiClient";
import type { AgentWorkspaceResponse } from "@/api/schemas";

// "Chat" leads (Persistent Brain Decision 3: conversation is the primary way to enter the
// Agent Workspace). Memory and Drafts are deliberately not here - both work invisibly in the
// background (memory quietly informs replies; a document-drafting-with-review workflow was
// removed entirely) and were confusing as standalone nav destinations. Writing Style stays -
// it's a real upload feature you might revisit, same as Research Documents.
const navItems = [
  { to: "/chat", label: "Chat", icon: ChatIcon },
  { to: "/documents", label: "Research Documents", icon: FileTextIcon },
  { to: "/style-profile", label: "Writing Style", icon: PencilLineIcon },
  { to: "/segments", label: "Project Segments", icon: StackIcon },
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
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<number | null>(null);
  const closeMenuButtonRef = useRef<HTMLButtonElement>(null);
  const deleteTriggerRefs = useRef<Record<number, HTMLButtonElement | null>>({});
  const previousConfirmingDeleteIdRef = useRef<number | null>(null);

  // Accessibility (found during an audit, 2026-10-09, and corrected after an actual browser
  // check caught it): focusing the trigger button synchronously inside Cancel's onClick looked
  // right but didn't work - at that point React hasn't re-rendered yet, so the ref still holds
  // null from the confirm block's own mount (the trigger button was unmounted when it opened).
  // Running this after commit, in an effect keyed on confirmingDeleteId, means the trigger
  // button has already been freshly (re)mounted and its ref populated by the time this runs.
  useEffect(() => {
    if (confirmingDeleteId === null && previousConfirmingDeleteIdRef.current !== null) {
      deleteTriggerRefs.current[previousConfirmingDeleteIdRef.current]?.focus();
    }
    previousConfirmingDeleteIdRef.current = confirmingDeleteId;
  }, [confirmingDeleteId]);

  // A route change (tapping a nav item, a conversation, or "New chat") means the user is done
  // with the sidebar on mobile - closing it automatically is what makes a phone/tablet sidebar
  // feel like a menu rather than a permanently obstructing panel. Desktop ignores this state
  // entirely (see the `lg:translate-x-0` class below), so this has no effect there.
  useEffect(() => {
    setIsSidebarOpen(false);
  }, [location.pathname]);

  // Accessibility (found during an audit, 2026-10-09): the mobile drawer previously had no
  // Escape-to-close and never moved focus into itself on open, so a keyboard user tabbing from
  // the hamburger button landed straight in the hidden main content behind the backdrop.
  useEffect(() => {
    if (!isSidebarOpen) return;
    closeMenuButtonRef.current?.focus();
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setIsSidebarOpen(false);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isSidebarOpen]);

  const conversationsQuery = useInfiniteQuery({
    queryKey: ["conversations"],
    queryFn: ({ pageParam }) => listConversations({ offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.hasMore ? allPages.reduce((total, page) => total + page.items.length, 0) : undefined,
  });
  // Backend order is oldest-first (a stable sort continued correctly across pages by offset) -
  // reversing the full flattened list still puts the most recent conversation first, the same
  // as reversing a single unpaginated page did before.
  const conversations = conversationsQuery.data?.pages.flatMap((page) => page.items) ?? [];

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
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:rounded-lg focus:bg-background focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-foreground focus:ring-2 focus:ring-ring"
      >
        Skip to content
      </a>
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
          <ListIcon className="size-5" />
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
            ref={closeMenuButtonRef}
            variant="ghost"
            size="sm"
            aria-label="Close menu"
            onClick={() => setIsSidebarOpen(false)}
            className="text-sidebar-foreground lg:hidden"
          >
            <XIcon className="size-5" />
          </Button>
        </div>
        <div className="px-3 pb-3">
          <Button
            className="w-full justify-start gap-2"
            variant="secondary"
            onClick={() => newChatMutation.mutate()}
            disabled={newChatMutation.isPending}
          >
            <PlusIcon className="size-4" />
            New chat
          </Button>
          {newChatMutation.isError && (
            <p role="alert" className="mt-2 px-1 text-xs text-destructive">
              {newChatMutation.error instanceof ApiError ? newChatMutation.error.message : "Could not start a chat."}
            </p>
          )}
        </div>

        <nav className="space-y-0.5 px-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm",
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
          {conversationsQuery.isError && (
            <div className="px-2 py-1">
              <p role="alert" className="text-xs text-destructive">
                {conversationsQuery.error instanceof ApiError
                  ? conversationsQuery.error.message
                  : "Could not load conversations."}
              </p>
              <button
                type="button"
                className="mt-1 text-xs underline"
                onClick={() => conversationsQuery.refetch()}
              >
                Try again
              </button>
            </div>
          )}
          {conversationsQuery.data && conversations.length === 0 && (
            <p className="px-2 py-1 text-xs text-sidebar-foreground/50">No conversations yet.</p>
          )}
          {conversations
            .slice()
            .reverse()
            .map((conversation) => (
              <div key={conversation.conversation_id} className="group relative">
                {confirmingDeleteId === conversation.conversation_id ? (
                  <div className="flex items-center justify-between gap-1 rounded-lg bg-sidebar-accent/60 py-1 pr-1 pl-2">
                    <span className="truncate text-xs text-sidebar-foreground">Delete this chat?</span>
                    <div className="flex shrink-0 gap-1">
                      <Button
                        size="xs"
                        variant="destructive"
                        disabled={deleteChatMutation.isPending}
                        onClick={() =>
                          deleteChatMutation.mutate(conversation.conversation_id, {
                            onSettled: () => setConfirmingDeleteId(null),
                          })
                        }
                      >
                        Delete
                      </Button>
                      <Button
                        // Accessibility (found during an audit, 2026-10-09): replacing the
                        // trigger button with this confirmation block used to drop keyboard
                        // focus to <body> with no follow-up. Autofocusing Cancel (the
                        // non-destructive default) here, and the effect above returning focus
                        // to the original trigger button once it's remounted, keeps focus
                        // somewhere meaningful throughout.
                        autoFocus
                        size="xs"
                        variant="ghost"
                        className="text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                        onClick={() => setConfirmingDeleteId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <NavLink
                      to={`/chat/${conversation.conversation_id}`}
                      className={({ isActive }) =>
                        cn(
                          "block truncate rounded-lg py-1.5 pr-7 pl-2 text-sm",
                          isActive
                            ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                            : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                        )
                      }
                    >
                      {conversation.title ?? "Untitled conversation"}
                    </NavLink>
                    <button
                      ref={(el) => {
                        deleteTriggerRefs.current[conversation.conversation_id] = el;
                      }}
                      type="button"
                      aria-label="Delete conversation"
                      onClick={(event) => {
                        event.preventDefault();
                        setConfirmingDeleteId(conversation.conversation_id);
                      }}
                      // Hover-to-reveal has no equivalent on touch - a lg:opacity-0 button would
                      // be permanently invisible and untappable on a phone, since there's no
                      // hover state to trigger it. Always visible below the lg breakpoint instead.
                      // Touch target (found during the 2026-10-09 accessibility audit): icon +
                      // p-1 padding was only 22x22px, under WCAG 2.5.8's 24x24px minimum -
                      // min-h-6/min-w-6 guarantee the floor without changing the visible icon size.
                      className="absolute top-1/2 right-1 flex min-h-6 min-w-6 -translate-y-1/2 items-center justify-center rounded p-1 text-sidebar-foreground/50 opacity-100 hover:bg-sidebar-accent hover:text-destructive lg:opacity-0 lg:group-hover:opacity-100"
                    >
                      <XIcon className="size-3.5" />
                    </button>
                  </>
                )}
              </div>
            ))}
          {conversationsQuery.hasNextPage && (
            <button
              type="button"
              disabled={conversationsQuery.isFetchingNextPage}
              onClick={() => conversationsQuery.fetchNextPage()}
              className="w-full px-2 py-1.5 text-left text-xs text-sidebar-foreground/60 underline hover:text-sidebar-foreground"
            >
              {conversationsQuery.isFetchingNextPage ? "Loading..." : "Load older conversations"}
            </button>
          )}
        </div>
        {deleteChatMutation.isError && (
          <p role="alert" className="border-t border-sidebar-border px-3 py-2 text-xs text-destructive">
            {deleteChatMutation.error instanceof ApiError
              ? deleteChatMutation.error.message
              : "Could not delete the conversation."}
          </p>
        )}

        <div className="border-t border-sidebar-border p-2">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm",
                isActive
                  ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
              )
            }
          >
            <GearIcon className="size-4" />
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
              <SignOutIcon className="size-4" />
              Log out
            </Button>
          </div>
        </div>
      </aside>

      {/* pt-14 clears the fixed mobile top bar (only rendered below lg) - lg:pt-0 removes it
          again once that bar is gone and the sidebar is static instead of fixed/overlaid. */}
      <main id="main-content" className="flex flex-1 flex-col overflow-hidden pt-14 lg:pt-0">
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
