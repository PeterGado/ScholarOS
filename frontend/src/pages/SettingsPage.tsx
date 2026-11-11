import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { connectGoogleAccount, getProfile, requestEmailVerification, setPassword, updateEmail } from "@/api/auth";
import { resetAgentWorkspace } from "@/api/agents";
import { ApiError } from "@/lib/apiClient";
import { useToast } from "@/lib/ToastContext";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useWorkspaceContext } from "@/components/WorkspaceGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";

const CONFIRMATION_WORD = "RESET";

// A dedicated Settings destination - the natural home for account-level actions (today just
// workspace reset; the natural place plans/billing would live if this ever needs them, without
// reshaping the rest of the app's navigation when that day comes).
export function SettingsPage() {
  useDocumentTitle("Settings");
  const workspace = useWorkspaceContext();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [confirmationText, setConfirmationText] = useState("");
  const [email, setEmail] = useState("");

  const profileQuery = useQuery({ queryKey: ["auth-profile"], queryFn: getProfile });

  useEffect(() => {
    if (profileQuery.data) setEmail(profileQuery.data.email ?? "");
  }, [profileQuery.data]);

  const emailMutation = useMutation({
    mutationFn: () => updateEmail(email.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth-profile"] });
      showToast("Email saved.");
    },
  });

  const verifyMutation = useMutation({
    mutationFn: requestEmailVerification,
    onSuccess: () => showToast("Verification email sent - check your inbox."),
  });

  const [newPassword, setNewPassword] = useState("");
  const setPasswordMutation = useMutation({
    mutationFn: () => setPassword(newPassword),
    onSuccess: () => {
      setNewPassword("");
      queryClient.invalidateQueries({ queryKey: ["auth-profile"] });
      showToast("Password set. You can now sign in with your email and password.");
    },
  });

  const connectGoogleMutation = useMutation({
    mutationFn: connectGoogleAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth-profile"] });
      showToast("Google account connected.");
    },
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
        <h1 className="text-2xl font-semibold tracking-tight leading-snug">Settings</h1>
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
            <Label htmlFor="account-email" className="text-sm text-muted-foreground">
              Email
            </Label>
            <p className="text-xs text-muted-foreground">
              Used for password reset and email verification links. Nothing else is sent here.
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
              <p role="alert" className="text-sm text-destructive">
                {emailMutation.error instanceof ApiError ? emailMutation.error.message : "Could not save email."}
              </p>
            )}
            {profileQuery.data?.email && !profileQuery.data.email_verified && (
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-warning">Not verified</span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={verifyMutation.isPending}
                  onClick={() => verifyMutation.mutate()}
                >
                  {verifyMutation.isPending ? "Sending..." : "Resend verification email"}
                </Button>
              </div>
            )}
            {profileQuery.data?.email_verified && <p className="text-sm text-success">Verified</p>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Security - connected accounts</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <p className="text-sm font-medium">Google</p>
            {profileQuery.data?.google_connected ? (
              <p className="text-sm text-success">Connected</p>
            ) : (
              <>
                <p className="text-xs text-muted-foreground">
                  Sign in with Google too. Connecting only adds this option - your existing sign-in keeps working.
                </p>
                <GoogleSignInButton onCredential={(idToken) => connectGoogleMutation.mutate(idToken)} />
              </>
            )}
            {connectGoogleMutation.isError && (
              <p role="alert" className="text-sm text-destructive">
                {connectGoogleMutation.error instanceof ApiError
                  ? connectGoogleMutation.error.message
                  : "Could not connect Google."}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Email and password</p>
            {profileQuery.data?.has_password ? (
              <p className="text-sm text-success">Password set</p>
            ) : (
              <form
                className="flex flex-wrap items-end gap-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  setPasswordMutation.mutate();
                }}
              >
                <div className="space-y-1">
                  <Label htmlFor="new-password" className="text-xs text-muted-foreground">
                    Choose a password (at least 12 characters)
                  </Label>
                  <Input
                    id="new-password"
                    type="password"
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="max-w-xs"
                  />
                </div>
                <Button type="submit" size="sm" disabled={setPasswordMutation.isPending || newPassword.length === 0}>
                  {setPasswordMutation.isPending ? "Saving..." : "Set password"}
                </Button>
              </form>
            )}
            {setPasswordMutation.isError && (
              <p role="alert" className="text-sm text-destructive">
                {setPasswordMutation.error instanceof ApiError
                  ? setPasswordMutation.error.message
                  : "Could not set password."}
              </p>
            )}
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
            <Label htmlFor="reset-confirm" className="text-xs font-medium text-muted-foreground">
              Type {CONFIRMATION_WORD} to confirm
            </Label>
            <Input
              id="reset-confirm"
              value={confirmationText}
              onChange={(e) => setConfirmationText(e.target.value)}
              placeholder={CONFIRMATION_WORD}
              className="max-w-xs"
            />
            {confirmationText.length > 0 && (
              <p className={`text-xs ${canReset ? "text-success" : "text-muted-foreground"}`}>
                {canReset ? "Confirmed - ready to permanently reset." : `Keep typing: "${CONFIRMATION_WORD}"`}
              </p>
            )}
          </div>
          <Button
            variant="destructive"
            disabled={!canReset || resetMutation.isPending}
            onClick={() => resetMutation.mutate()}
          >
            {resetMutation.isPending ? "Resetting..." : "Permanently reset my workspace"}
          </Button>
          {resetMutation.isError && (
            <p role="alert" className="text-sm text-destructive">
              {resetMutation.error instanceof ApiError ? resetMutation.error.message : "Could not reset workspace."}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
