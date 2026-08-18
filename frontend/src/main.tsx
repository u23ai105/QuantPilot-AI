import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { Providers } from "./app/providers";
import { AuthProvider } from "./features/auth/AuthContext";
import { router } from "./app/router";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Providers>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </Providers>
  </React.StrictMode>
);
