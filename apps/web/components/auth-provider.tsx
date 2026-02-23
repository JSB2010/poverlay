"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signOut as firebaseSignOut,
  updateProfile,
  type User,
} from "firebase/auth";
import {
  ensureFirebaseAuthPersistence,
  getFirebaseAuth,
  isFirebaseAuthEnabled,
} from "@/lib/auth/firebase-client";
import { apiUrl } from "@/lib/api-base";
import { PUBLIC_WEB_CONFIG } from "@/lib/public-config";

type AuthAccount = {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
};

type AuthContextValue = {
  isEnabled: boolean;
  isLoading: boolean;
  isAccessLoading: boolean;
  account: AuthAccount | null;
  isAdmin: boolean;
  adminConfigured: boolean;
  getIdToken: (forceRefresh?: boolean) => Promise<string | null>;
  refreshAccess: () => Promise<void>;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signUpWithPassword: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  sendPasswordReset: (email: string) => Promise<void>;
  updateProfileMetadata: (payload: { displayName: string; photoURL: string }) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const CONFIGURED_API_BASE = PUBLIC_WEB_CONFIG.apiBase;

type UserAccessResponse = {
  is_admin?: boolean;
  admin_configured?: boolean;
};

function buildApiUrl(path: string): string {
  return apiUrl(path, CONFIGURED_API_BASE);
}

async function readApiPayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  return null;
}

function mapUser(user: User): AuthAccount {
  return {
    uid: user.uid,
    email: user.email,
    displayName: user.displayName,
    photoURL: user.photoURL,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<AuthAccount | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAccessLoading, setIsAccessLoading] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminConfigured, setAdminConfigured] = useState(false);
  const isEnabled = isFirebaseAuthEnabled();

  useEffect(() => {
    if (!isEnabled) {
      setAccount(null);
      setIsLoading(false);
      setIsAccessLoading(false);
      setIsAdmin(false);
      setAdminConfigured(false);
      return;
    }

    const auth = getFirebaseAuth();
    void ensureFirebaseAuthPersistence().catch(() => {
      // onAuthStateChanged still hydrates user state even if persistence setting fails.
    });

    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setAccount(user ? mapUser(user) : null);
      setIsLoading(false);
      if (!user) {
        setIsAccessLoading(false);
        setIsAdmin(false);
        setAdminConfigured(false);
      }
    });

    return unsubscribe;
  }, [isEnabled]);

  const getIdToken = useCallback(async (forceRefresh = false): Promise<string | null> => {
    if (!isEnabled) {
      return null;
    }
    const auth = getFirebaseAuth();
    if (!auth.currentUser) {
      return null;
    }
    return auth.currentUser.getIdToken(forceRefresh);
  }, [isEnabled]);

  const refreshAccess = useCallback(async (): Promise<void> => {
    if (!isEnabled) {
      setIsAccessLoading(false);
      setIsAdmin(false);
      setAdminConfigured(false);
      return;
    }

    const auth = getFirebaseAuth();
    const user = auth.currentUser;
    if (!user) {
      setIsAccessLoading(false);
      setIsAdmin(false);
      setAdminConfigured(false);
      return;
    }

    setIsAccessLoading(true);
    try {
      const token = await user.getIdToken();
      const response = await fetch(buildApiUrl("/api/user/access"), {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      const payload = (await readApiPayload(response)) as UserAccessResponse | null;
      if (!response.ok) {
        setIsAdmin(false);
        setAdminConfigured(false);
        return;
      }

      setIsAdmin(Boolean(payload?.is_admin));
      setAdminConfigured(Boolean(payload?.admin_configured));
    } catch {
      setIsAdmin(false);
      setAdminConfigured(false);
    } finally {
      setIsAccessLoading(false);
    }
  }, [isEnabled]);

  useEffect(() => {
    if (!account?.uid || !isEnabled) {
      setIsAccessLoading(false);
      setIsAdmin(false);
      setAdminConfigured(false);
      return;
    }
    void refreshAccess();
  }, [account?.uid, isEnabled, refreshAccess]);

  const signInWithPassword = useCallback(async (email: string, password: string): Promise<void> => {
    if (!isEnabled) {
      throw new Error("Authentication is disabled.");
    }
    const auth = getFirebaseAuth();
    await ensureFirebaseAuthPersistence();
    await signInWithEmailAndPassword(auth, email, password);
  }, [isEnabled]);

  const signUpWithPassword = useCallback(async (email: string, password: string): Promise<void> => {
    if (!isEnabled) {
      throw new Error("Authentication is disabled.");
    }
    const auth = getFirebaseAuth();
    await ensureFirebaseAuthPersistence();
    await createUserWithEmailAndPassword(auth, email, password);
  }, [isEnabled]);

  const signOut = useCallback(async (): Promise<void> => {
    if (!isEnabled) {
      return;
    }
    await firebaseSignOut(getFirebaseAuth());
  }, [isEnabled]);

  const sendPasswordReset = useCallback(async (email: string): Promise<void> => {
    if (!isEnabled) {
      throw new Error("Authentication is disabled.");
    }
    await sendPasswordResetEmail(getFirebaseAuth(), email);
  }, [isEnabled]);

  const updateProfileMetadata = useCallback(
    async (payload: { displayName: string; photoURL: string }): Promise<void> => {
      if (!isEnabled) {
        throw new Error("Authentication is disabled.");
      }

      const auth = getFirebaseAuth();
      const user = auth.currentUser;
      if (!user) {
        throw new Error("No active account.");
      }

      await updateProfile(user, {
        displayName: payload.displayName.trim() || null,
        photoURL: payload.photoURL.trim() || null,
      });
      await user.reload();

      if (!auth.currentUser) {
        setAccount(null);
        return;
      }
      setAccount(mapUser(auth.currentUser));
    },
    [isEnabled],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      isEnabled,
      isLoading,
      isAccessLoading,
      account,
      isAdmin,
      adminConfigured,
      getIdToken,
      refreshAccess,
      signInWithPassword,
      signUpWithPassword,
      signOut,
      sendPasswordReset,
      updateProfileMetadata,
    }),
    [
      account,
      adminConfigured,
      getIdToken,
      isEnabled,
      isAccessLoading,
      isAdmin,
      isLoading,
      refreshAccess,
      sendPasswordReset,
      signInWithPassword,
      signOut,
      signUpWithPassword,
      updateProfileMetadata,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return value;
}
