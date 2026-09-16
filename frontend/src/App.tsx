import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { WorkspaceGate } from "@/components/WorkspaceGate";
import { AppShell } from "@/components/AppShell";
import { LoginPage } from "@/pages/LoginPage";
import { OnboardingPage } from "@/pages/OnboardingPage";
import { DocumentsPage } from "@/pages/DocumentsPage";
import { StyleProfilePage } from "@/pages/StyleProfilePage";
import { DraftsPage } from "@/pages/DraftsPage";
import { DraftDetailPage } from "@/pages/DraftDetailPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
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
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/style-profile" element={<StyleProfilePage />} />
            <Route path="/drafts" element={<DraftsPage />} />
            <Route path="/drafts/:draftId" element={<DraftDetailPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/drafts" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
