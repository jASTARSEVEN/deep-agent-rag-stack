/** React 前端應用程式路由與 auth provider 入口。 */

import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "../auth/AuthProvider";
import { ProtectedRoute } from "../auth/ProtectedRoute";
import { AuthCallbackPage } from "../pages/AuthCallbackPage";
import { AreasPage } from "../pages/AreasPage";
import { HomePage } from "../pages/HomePage";


/** 應用程式根元件。 */
export function App(): JSX.Element {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<HomePage />} path="/" />
          <Route element={<AuthCallbackPage />} path="/auth/callback" />
          <Route
            element={
              <ProtectedRoute>
                <AreasPage />
              </ProtectedRoute>
            }
            path="/areas"
          />
          <Route element={<Navigate replace to="/" />} path="*" />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
