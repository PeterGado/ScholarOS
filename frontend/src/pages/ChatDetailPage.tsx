import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Navigate, useParams } from "react-router-dom";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getChatReplyStatus, listConversationMessages, listWritingSegments, retryChatReply, sendChatMessage } from "@/api/writing";
import { WRITING_SEGMENTS_QUERY_KEY } from "@/pages/SegmentsPage";
import { DEFAULT_LIST_LIMIT } from "@/api/pagination";
import { ApiError } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { EmailVerificationNotice } from "@/components/EmailVerificationNotice";
import { MarkdownMessage } from "@/components/MarkdownMessage";
import { ThinkingIndicator } from "@/components/ThinkingIndicator";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";

const REPLY_POLL_INTERVAL_MS = 1500;
const IN_FLIGHT_STATES = new Set(["queued", "running"]);

interface ActiveReply {
  conversationId: number;
  workItemId: number;
  startedAt: number;
}

function activeReplyStorageKey(conversationId: number) {
  return `scholaros:chat-reply:${conversationId}`;
}

function loadActiveReply(conversationId: number): ActiveReply | null {
  try {
    const raw = window.sessionStorage.getItem(activeReplyStorageKey(conversationId));
    if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (
      typeof value === "object" &&
      value !== null &&
      "conversationId" in value &&
      "workItemId" in value &&
      typeof value.conversationId === "number" &&
      typeof value.workItemId === "number" &&
      value.conversationId === conversationId
    ) {
      // startedAt predates this field on an already-stored value (pre-2026-10-06) - fall back
      // to "now" rather than drop a resumable in-flight reply entirely.
      const startedAt = "startedAt" in value && typeof value.startedAt === "number" ? value.startedAt : Date.now();
      return { conversationId: value.conversationId, workItemId: value.workItemId, startedAt };
    }
  } catch {
    // Session storage is a convenience for restoring an in-flight reply, never a dependency.
  }
  return null;
}

// A single conversation thread, styled like Claude/ChatGPT: full-width alternating rows, an
// auto-growing input pinned to the bottom, Enter to send. Reply completion is observed by
// polling the reply's own real Work Item status (state/last_error) rather than guessing from a
// fixed timeout - a genuinely failed reply used to be indistinguishable from a slow one, with
// no explanation and no way to recover short of sending the message again.
export function ChatDetailPage() {
  const { conversationId: conversationIdParam } = useParams<{ conversationId: string }>();
  const conversationId = Number(conversationIdParam);

  if (!Number.isInteger(conversationId) || conversationId < 1) {
    return <Navigate to="/chat" replace />;
  }

  return <ChatConversation conversationId={conversationId} />;
}

function ChatConversation({ conversationId }: { conversationId: number }) {
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [selectedSegmentId, setSelectedSegmentId] = useState<number | null>(null);
  const [activeReply, setActiveReply] = useState<ActiveReply | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const isLoadingOlderRef = useRef(false);
  const activeWorkItemId = activeReply?.conversationId === conversationId ? activeReply.workItemId : null;

  const trackActiveReply = useCallback((workItemId: number | null) => {
    if (workItemId === null) {
      try {
        window.sessionStorage.removeItem(activeReplyStorageKey(conversationId));
      } catch {
        // Storage can be disabled by the browser; the in-memory state still works.
      }
      setActiveReply(null);
      return;
    }
    const reply = { conversationId, workItemId, startedAt: Date.now() };
    try {
      window.sessionStorage.setItem(activeReplyStorageKey(conversationId), JSON.stringify(reply));
    } catch {
      // Storage is only used to recover after navigation or a reload.
    }
    setActiveReply(reply);
  }, [conversationId]);

  // A reply continues on the backend even if the user reloads or follows a sidebar link.
  // Restore its Work Item so this page resumes polling instead of leaving the last user
  // message looking unanswered forever.
  useEffect(() => {
    setActiveReply(loadActiveReply(conversationId));
    setContent("");
    setSelectedSegmentId(null);
  }, [conversationId]);

  // offset=0 is the tail of the conversation (most recent messages), not the start - each
  // fetched page is oldest-first internally, but pages themselves arrive newest-first (the
  // first page fetched is the most recent one). "Load older" appends the next-older page to
  // `data.pages`, so the pages array is reversed before flattening to get true chronological
  // order for display.
  const messagesQuery = useInfiniteQuery({
    queryKey: ["conversation-messages", conversationId],
    queryFn: ({ pageParam }) => listConversationMessages(conversationId, { limit: DEFAULT_LIST_LIMIT, offset: pageParam }),
    initialPageParam: 0,
    // Advanced by the requested page size, not by how many messages were actually returned -
    // a page can come back with fewer visible messages than `limit` when some of its rows were
    // rolling summaries (filtered out server-side), and offset must still track raw DB rows
    // consumed so no real message is ever skipped.
    getNextPageParam: (lastPage, allPages) => (lastPage.hasMore ? allPages.length * DEFAULT_LIST_LIMIT : undefined),
  });
  const messages = messagesQuery.data?.pages.slice().reverse().flatMap((page) => page.items) ?? [];

  function loadOlderMessages() {
    isLoadingOlderRef.current = true;
    messagesQuery.fetchNextPage();
  }

  const replyStatusQuery = useQuery({
    queryKey: ["chat-reply-status", conversationId, activeWorkItemId],
    queryFn: () => getChatReplyStatus(conversationId, activeWorkItemId!),
    enabled: activeWorkItemId !== null,
    refetchInterval: (query) => (IN_FLIGHT_STATES.has(query.state.data?.state ?? "") ? REPLY_POLL_INTERVAL_MS : false),
  });

  const replyState = replyStatusQuery.data?.state;
  // A poll failure (network/5xx on the status check itself, not the generation) is treated the
  // same as a failed reply rather than left spinning forever with nothing left to retry it -
  // React Query's own retries are already exhausted by the time isError is true here.
  const replyFailed = replyState === "failed" || replyStatusQuery.isError;
  const isWaitingForReply =
    activeWorkItemId !== null && !replyFailed && (replyState === undefined || IN_FLIGHT_STATES.has(replyState));

  useEffect(() => {
    if (replyState === "succeeded") {
      queryClient.invalidateQueries({ queryKey: ["conversation-messages", conversationId] });
      trackActiveReply(null);
    }
  }, [replyState, conversationId, queryClient, trackActiveReply]);

  useEffect(() => {
    // A "Load older messages" click also changes messagesQuery.data (a new page is appended),
    // but it should never yank the view back to the bottom while the user is reading history -
    // only the initial load and a genuinely new message at the tail should autoscroll.
    if (isLoadingOlderRef.current) {
      isLoadingOlderRef.current = false;
      return;
    }
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messagesQuery.data]);

  const segmentsQuery = useQuery({ queryKey: WRITING_SEGMENTS_QUERY_KEY, queryFn: listWritingSegments });
  const segments = segmentsQuery.data ?? [];

  const sendMutation = useMutation({
    mutationFn: (message: string) =>
      sendChatMessage(conversationId, message, selectedSegmentId ?? undefined),
    onSuccess: (status, message) => {
      queryClient.invalidateQueries({ queryKey: ["conversation-messages", conversationId] });
      trackActiveReply(status.work_item_id);
      if (content === message) setContent("");
    },
  });

  const retryMutation = useMutation({
    mutationFn: () => retryChatReply(conversationId, activeWorkItemId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-reply-status", conversationId, activeWorkItemId] });
      // A retry is a genuinely new attempt - restart the elapsed-time clock the thinking
      // indicator's staged labels are based on, rather than carry over the failed attempt's.
      trackActiveReply(activeWorkItemId!);
    },
  });

  function handleSend() {
    if (!content.trim() || sendMutation.isPending || isWaitingForReply) return;
    sendMutation.mutate(content);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div ref={scrollRef} className="flex-1 space-y-6 overflow-y-auto px-6 py-6">
        {messagesQuery.isLoading && (
          <div className="mx-auto max-w-2xl space-y-3" aria-label="Loading messages">
            <Skeleton className="h-16 w-2/3" />
            <Skeleton className="ml-auto h-12 w-1/2" />
            <Skeleton className="h-20 w-3/4" />
          </div>
        )}
        {messagesQuery.isError && (
          <Alert>
            <AlertDescription className="text-destructive">
              {messagesQuery.error instanceof ApiError ? messagesQuery.error.message : "Could not load this conversation."}
            </AlertDescription>
            <Button size="sm" variant="outline" className="mt-2" onClick={() => messagesQuery.refetch()}>
              Try again
            </Button>
          </Alert>
        )}
        {messagesQuery.hasNextPage && (
          <div className="mx-auto max-w-2xl text-center">
            <button
              type="button"
              disabled={messagesQuery.isFetchingNextPage}
              onClick={loadOlderMessages}
              className="text-xs text-muted-foreground underline hover:text-foreground"
            >
              {messagesQuery.isFetchingNextPage ? "Loading..." : "Load older messages"}
            </button>
          </div>
        )}
        {messages.map((message) =>
          message.direction === "user_request" ? (
            <div key={message.message_id} className="mx-auto max-w-2xl rounded-xl bg-muted px-4 py-3">
              <p className="mb-1 text-xs font-medium text-muted-foreground">You</p>
              <MarkdownMessage content={message.content} />
            </div>
          ) : (
            <div key={message.message_id} className="mx-auto max-w-2xl">
              <p className="mb-1 text-xs font-medium text-muted-foreground">Assistant</p>
              <MarkdownMessage content={message.content} />
            </div>
          ),
        )}
        {isWaitingForReply && !replyFailed && activeReply && (
          <div className="mx-auto max-w-2xl">
            <p className="mb-1 text-xs font-medium text-muted-foreground">Assistant</p>
            <ThinkingIndicator startedAt={activeReply.startedAt} />
          </div>
        )}
        {replyFailed && replyStatusQuery.data && (
          <Alert>
            <AlertTitle>Reply failed</AlertTitle>
            <AlertDescription>
              {replyStatusQuery.data?.last_error ?? "The assistant could not generate a reply."}
            </AlertDescription>
            <Button
              size="sm"
              variant="outline"
              className="mt-2"
              disabled={retryMutation.isPending}
              onClick={() => retryMutation.mutate()}
            >
              {retryMutation.isPending ? "Retrying..." : "Retry"}
            </Button>
            {retryMutation.isError && (
              <p className="mt-2 text-sm text-destructive">
                {retryMutation.error instanceof ApiError ? retryMutation.error.message : "Could not retry."}
              </p>
            )}
          </Alert>
        )}
        {replyStatusQuery.isError && !replyStatusQuery.data && (
          <Alert>
            <AlertDescription className="text-destructive">
              {replyStatusQuery.error instanceof ApiError
                ? replyStatusQuery.error.message
                : "Could not check the assistant reply status."}
            </AlertDescription>
            <Button size="sm" variant="outline" className="mt-2" onClick={() => replyStatusQuery.refetch()}>
              Check again
            </Button>
          </Alert>
        )}
      </div>

      <div className="border-t border-border p-4">
        {segments.length > 0 && (
          <div className="mx-auto mb-2 max-w-2xl">
            <select
              value={selectedSegmentId ?? ""}
              onChange={(e) => setSelectedSegmentId(e.target.value ? Number(e.target.value) : null)}
              aria-label="Project segment"
              className="rounded-lg border border-input bg-transparent px-2 py-1 text-xs text-muted-foreground"
            >
              <option value="">No segment selected</option>
              {segments.map((segment) => (
                <option key={segment.segment_id} value={segment.segment_id}>
                  {segment.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="mx-auto flex max-w-2xl items-end gap-2">
          <Textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message your Agent Workspace... (Enter to send, Shift+Enter for a new line)"
            rows={1}
            className="max-h-40 resize-none"
          />
          <Button onClick={handleSend} disabled={sendMutation.isPending || isWaitingForReply || !content.trim()}>
            Send
          </Button>
        </div>
        {sendMutation.isError &&
          (sendMutation.error instanceof ApiError && sendMutation.error.errorType === "EmailNotVerifiedError" ? (
            <div className="mx-auto mt-2 max-w-2xl">
              <EmailVerificationNotice />
            </div>
          ) : (
            <p className="mx-auto mt-2 max-w-2xl text-sm text-destructive">
              {sendMutation.error instanceof ApiError ? sendMutation.error.message : "Could not send message."}
            </p>
          ))}
      </div>
    </div>
  );
}
