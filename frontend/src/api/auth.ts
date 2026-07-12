import api from "./index";
import type { ApiResponse, AuthResponse } from "@/types";

export interface LoginParams {
  username: string;
  password: string;
}

export interface RegisterParams {
  username: string;
  password: string;
  email: string;
  nickname?: string;
}

export const authApi = {
  login: (data: LoginParams) =>
    api.post<ApiResponse<AuthResponse>>("/auth/login", data),

  register: (data: RegisterParams) =>
    api.post<ApiResponse<AuthResponse>>("/auth/register", data),
};