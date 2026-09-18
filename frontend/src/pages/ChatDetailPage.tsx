import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getChatReplyStatus, listConversationMessages, retryChatReply, sendChatMessage } from "@/api/writing";
import { ApiError } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { MarkdownMessage } from "@/components/MarkdownMessage";

const REPLY_POLL_INTERVAL_MS = 1500;
const IN_FLIGHT_STATES = new Set(["queued", "running"]);

// A single conversation thread, styled like Claude/ChatGPT: full-width alternating rows, an
// auto-growing input pinned to the bottom, Enter to send. Reply completion is observed by
// polling the reply's own real Work Item status (state/last_error) rather than guessing from a
// fixed timeout - a genuinely failed reply used to be indistinguishable from a slow one, with
// no explanation and no way to recover short of sending the message again.
export function ChatDetailPage() {
  const { conversationId: conversationIdParam } = useParams<{ conversationId: string }>();
  const conversationId = Number(conversationIdParam);
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [activeWorkItemId, setActiveWorkItemId] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const messagesQuery = useQuery({
    queryKey: ["conversation-messages", conversationId],
    queryFn: () => listConversationMessages(conversationId),
  });

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
      setActiveWorkItemId(null);
    }
  }, [replyState, conversationId, queryClient]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messagesQuery.data]);

  const sendMutation = useMutation({
    mutationFn: (message: string) => sendChatMessage(conversationId, message),
    onSuccess: (status) => {
      queryClient.invalidateQueries({ queryKey: ["conversation-messages", conversationId] });
      setActiveWorkItemId(status.work_item_id);
    },
  });

  const retryMutation = useMutation({
    mutationFn: () => retryChatReply(conversationId, activeWorkItemId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-reply-status", conversationId, activeWorkItemId] });
    },
  });

  function handleSend() {
    if (!content.trim() || sendMutation.isPending || isWaitingForReply) return;
    sendMutation.mutate(content);
    setContent("");
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
        {messagesQuery.isLoading && <p className="text-sm text-muted-foreground">Loading messages...</p>}
        {messagesQuery.data?.map((message) =>
          message.direction === "user_request" ? (
            <div key={message.message_id} className="mx-auto max-w-2xl rounded-2xl bg-muted px-4 py-3">
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
        {isWaitingForReply && !replyFailed && (
          <div className="mx-auto max-w-2xl">
            <p className="mb-1 text-xs font-medium text-muted-foreground">Assistant</p>
            <p className="text-sm text-muted-foreground">Thinking...</p>
          </div>
        )}
        {replyFailed && (
          <div className="mx-auto max-w-2xl rounded-lg border border-destructive/50 bg-destructive/5 px-4 py-3">
            <p className="mb-1 text-xs font-medium text-destructive">Reply failed</p>
            <p className="text-sm text-muted-foreground">
              {replyStatusQuery.data?.last_error ?? "The assistant could not generate a reply."}
            </p>
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
          </div>
        )}
      </div>

      <div className="border-t border-border p-4">
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
        {sendMutation.isError && (
          <p className="mx-auto mt-2 max-w-2xl text-sm text-destructive">
            {sendMutation.error instanceof ApiError ? sendMutation.error.message : "Could not send message."}
          </p>
        )}
      </div>
    </div>
  );
}
