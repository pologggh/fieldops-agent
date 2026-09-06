export type Role = 'admin' | 'operator' | 'viewer';

export interface User {
  email: string;
  name: string;
  role: Role;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}
