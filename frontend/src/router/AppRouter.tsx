import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ChatPage from "../pages/ChatPage";
import SQLToolPage from "../pages/SQLToolPage";
import VectorToolPage from "../pages/VectorToolPage";
import LoginPage from "../pages/LoginPage";
import { AuthProvider } from "../auth/AuthContext";
import { RateLimitProvider } from "../auth/RateLimitContext";
import ProtectedRoute from "../auth/ProtectedRoute";

const AppRouter: React.FC = () => (
  <BrowserRouter>
    <AuthProvider>
      <RateLimitProvider>
      <Routes>
        <Route path="/" element={<LoginPage />} />

        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sql"
          element={
            <ProtectedRoute>
              <SQLToolPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vector"
          element={
            <ProtectedRoute>
              <VectorToolPage />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </RateLimitProvider>
    </AuthProvider>
  </BrowserRouter>
);

export default AppRouter;
