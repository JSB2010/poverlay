export type AuthMethodId = "password" | "google";

export type AuthMethod = {
  id: AuthMethodId;
  label: string;
  enabled: boolean;
  description: string;
};

export const AUTH_METHODS: AuthMethod[] = [
  {
    id: "password",
    label: "Email and password",
    enabled: true,
    description: "Sign in with an email address and password.",
  },
  {
    id: "google",
    label: "Google Sign-In",
    enabled: false,
    description: "Planned provider. Not enabled in this phase.",
  },
];
