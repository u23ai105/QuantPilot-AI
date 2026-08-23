import { fetchClient } from "./client";
import type { LoginRequest, RegisterRequest, TokenResponse, UserResponse } from "../../types/auth";

export const authApi = {
  login: (data: LoginRequest) =>
    fetchClient<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  register: (data: RegisterRequest) =>
    fetchClient<UserResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  me: () =>
    fetchClient<UserResponse>("/auth/me", {
      method: "GET",
    }),
};
