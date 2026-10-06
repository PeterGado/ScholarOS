import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ChatCircleIcon } from "@phosphor-icons/react";
import { startConversation } from "@/api/writing";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

// The empty state shown at /chat (no conversation selected yet) - the sidebar and layout
// itself come from ChatLayout, which wraps this via <Outlet/>.
export function ChatPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const newChatMutation = useMutation({
    mutationFn: () => startConversation(),
    onSuccess: (conversation) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      navigate(`/chat/${conversation.conversation_id}`);
    },
  });

  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <EmptyState
        icon={ChatCircleIcon}
        title="Your Agent Workspace"
        description="Start a conversation - it automatically uses your project context, research, writing style, and memory."
        action={
          <Button onClick={() => newChatMutation.mutate()} disabled={newChatMutation.isPending}>
            {newChatMutation.isPending ? "Starting..." : "New chat"}
          </Button>
        }
        className="max-w-md border-none"
      />
    </div>
  );
}
