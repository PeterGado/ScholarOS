import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { startConversation } from "@/api/writing";
import { Button } from "@/components/ui/button";

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
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
      <h1 className="text-lg font-semibold">Your Agent Workspace</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        Start a conversation - it automatically uses your project context, research, writing
        style, and memory.
      </p>
      <Button onClick={() => newChatMutation.mutate()} disabled={newChatMutation.isPending}>
        {newChatMutation.isPending ? "Starting..." : "New chat"}
      </Button>
    </div>
  );
}
