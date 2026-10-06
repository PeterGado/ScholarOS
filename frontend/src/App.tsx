import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { WorkspaceGate } from "@/components/WorkspaceGate";
import { AppShell } from "@/components/AppShell";
import { LandingPage } from "@/pages/LandingPage";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { ResetPasswordPage } from "@/pages/ResetPasswordPage";
import { VerifyEmailPage } from "@/pages/VerifyEmailPage";
import { OnboardingPage } from "@/pages/OnboardingPage";
import { DocumentsPage } from "@/pages/DocumentsPage";
import { StyleProfilePage } from "@/pages/StyleProfilePage";
import { ChatPage } from "@/pages/ChatPage";
import { ChatDetailPage } from "@/pages/ChatDetailPage";
import { MemoryPage } from "@/pages/MemoryPage";
import { SegmentsPage } from "@/pages/SegmentsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { PrivacyPage } from "@/pages/PrivacyPage";
import { TermsPage } from "@/pages/TermsPage";

function App() {
  return (
    <BrowserRouter>
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
    </BrowserRouter>
  );
}

export default App;
