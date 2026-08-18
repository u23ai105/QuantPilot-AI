import { fetchClient } from "./client";
import type { LoginRequest, TokenResponse, UserResponse } from "../../types/auth";

export const authApi = {
  login: (data: LoginRequest) =>
    fetchClient<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  me: () =>
    fetchClient<UserResponse>("/auth/me", {
      method: "GET",
    }),
};
