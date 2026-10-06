import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getProfile, updateEmail } from "@/api/auth";
import { resetAgentWorkspace } from "@/api/agents";
import { ApiError } from "@/lib/apiClient";
import { useWorkspaceContext } from "@/components/WorkspaceGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const CONFIRMATION_WORD = "RESET";

// A dedicated Settings destination - the natural home for account-level actions (today just
// workspace reset; the natural place plans/billing would live if this ever needs them, without
// reshaping the rest of the app's navigation when that day comes).
export function SettingsPage() {
  const workspace = useWorkspaceContext();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirmationText, setConfirmationText] = useState("");
  const [email, setEmail] = useState("");

  const profileQuery = useQuery({ queryKey: ["auth-profile"], queryFn: getProfile });

  useEffect(() => {
    if (profileQuery.data) setEmail(profileQuery.data.email ?? "");
  }, [profileQuery.data]);

  const emailMutation = useMutation({
    mutationFn: () => updateEmail(email.trim()),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["auth-profile"] }),
  });

  const resetMutation = useMutation({
    mutationFn: resetAgentWorkspace,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["agent-workspace"] });
      navigate("/onboarding");
    },
  });

  const canReset = confirmationText === CONFIRMATION_WORD;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-lg font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Signed in workspace: <span className="font-medium text-foreground">{workspace.project.title}</span>
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">Username</p>
            <p className="text-sm font-medium">
              {profileQuery.isLoading
                ? "Loading..."
                : profileQuery.data
                  ? profileQuery.data.username
                  : "Could not load account info."}
            </p>
          </div>
          <div className="space-y-2">
            <label htmlFor="account-email" className="text-sm text-muted-foreground">
              Email
            </label>
            <p className="text-xs text-muted-foreground">
              Used only for password reset links. Nothing else is sent here.
            </p>
            <div className="flex items-end gap-3">
              <Input
                id="account-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="max-w-xs"
                disabled={profileQuery.isLoading}
              />
              <Button
                size="sm"
                disabled={emailMutation.isPending || !email.trim() || email === (profileQuery.data?.email ?? "")}
                onClick={() => emailMutation.mutate()}
              >
                {emailMutation.isPending ? "Saving..." : "Save email"}
              </Button>
            </div>
            {emailMutation.isError && (
              <p className="text-sm text-destructive">
                {emailMutation.error instanceof ApiError ? emailMutation.error.message : "Could not save email."}
              </p>
            )}
            {emailMutation.isSuccess && <p className="text-sm text-muted-foreground">Email saved.</p>}
          </div>
        </CardContent>
      </Card>

      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="text-sm text-destructive">Danger zone</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium">Reset workspace</p>
            <p className="text-sm text-muted-foreground">
              Permanently deletes your Project, research documents, extracted knowledge, writing
              style, memory, and conversations, so you can go through onboarding again from a
              clean slate. This cannot be undone.
            </p>
          </div>
          <div className="space-y-2">
            <label htmlFor="reset-confirm" className="text-xs font-medium text-muted-foreground">
              Type {CONFIRMATION_WORD} to confirm
            </label>
            <Input
              id="reset-confirm"
              value={confirmationText}
              onChange={(e) => setConfirmationText(e.target.value)}
              placeholder={CONFIRMATION_WORD}
              className="max-w-xs"
            />
          </div>
          <Button
            variant="destructive"
            disabled={!canReset || resetMutation.isPending}
            onClick={() => resetMutation.mutate()}
          >
            {resetMutation.isPending ? "Resetting..." : "Permanently reset my workspace"}
          </Button>
          {resetMutation.isError && (
            <p className="text-sm text-destructive">
              {resetMutation.error instanceof ApiError ? resetMutation.error.message : "Could not reset workspace."}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
