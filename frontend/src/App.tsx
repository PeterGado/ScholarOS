import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { WorkspaceGate } from "@/components/WorkspaceGate";
import { AppShell } from "@/components/AppShell";

// Every page is route-split (2026-10-10, frontend audit finding: the single bundle was 772KB
// minified/230KB gzipped and only going to grow with the next milestone's new domain) - each
// becomes its own chunk, fetched only when its route is actually visited, instead of every
// page's code shipping in the one bundle every visitor downloads just to see the landing page
// or log in. React.lazy + Suspense is the standard RR6/Vite pattern for this; no new dependency.
const LandingPage = lazy(() => import("@/pages/LandingPage").then((m) => ({ default: m.LandingPage })));
const LoginPage = lazy(() => import("@/pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import("@/pages/RegisterPage").then((m) => ({ default: m.RegisterPage })));
const ForgotPasswordPage = lazy(() =>
  import("@/pages/ForgotPasswordPage").then((m) => ({ default: m.ForgotPasswordPage })),
);
const ResetPasswordPage = lazy(() =>
  import("@/pages/ResetPasswordPage").then((m) => ({ default: m.ResetPasswordPage })),
);
const VerifyEmailPage = lazy(() => import("@/pages/VerifyEmailPage").then((m) => ({ default: m.VerifyEmailPage })));
const OnboardingPage = lazy(() => import("@/pages/OnboardingPage").then((m) => ({ default: m.OnboardingPage })));
const DocumentsPage = lazy(() => import("@/pages/DocumentsPage").then((m) => ({ default: m.DocumentsPage })));
const StyleProfilePage = lazy(() =>
  import("@/pages/StyleProfilePage").then((m) => ({ default: m.StyleProfilePage })),
);
const ChatPage = lazy(() => import("@/pages/ChatPage").then((m) => ({ default: m.ChatPage })));
const ChatDetailPage = lazy(() => import("@/pages/ChatDetailPage").then((m) => ({ default: m.ChatDetailPage })));
const MemoryPage = lazy(() => import("@/pages/MemoryPage").then((m) => ({ default: m.MemoryPage })));
const SegmentsPage = lazy(() => import("@/pages/SegmentsPage").then((m) => ({ default: m.SegmentsPage })));
const SettingsPage = lazy(() => import("@/pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage })));
const PrivacyPage = lazy(() => import("@/pages/PrivacyPage").then((m) => ({ default: m.PrivacyPage })));
const TermsPage = lazy(() => import("@/pages/TermsPage").then((m) => ({ default: m.TermsPage })));

// Matches WorkspaceGate's own loading-state copy/styling (components/WorkspaceGate.tsx) so a
// route-chunk fetch reads the same as every other "loading something" state in this app.
function RouteFallback() {
  return <p className="p-6 text-sm text-muted-foreground">Loading...</p>;
}

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/terms" element={<TermsPage />} />
          <Route
            path="/onboarding"
            element={
              <ProtectedRoute>
                <OnboardingPage />
              </ProtectedRoute>
            }
          />
          <Route
            element={
              <ProtectedRoute>
                <WorkspaceGate />
              </ProtectedRoute>
            }
          >
            <Route element={<AppShell />}>
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/chat/:conversationId" element={<ChatDetailPage />} />
              <Route path="/documents" element={<DocumentsPage />} />
              <Route path="/style-profile" element={<StyleProfilePage />} />
              <Route path="/segments" element={<SegmentsPage />} />
              <Route path="/memory" element={<MemoryPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
