"use client";

import { initializeApp, getApp, getApps, type FirebaseApp } from "firebase/app";
import { browserLocalPersistence, getAuth, setPersistence, type Auth } from "firebase/auth";
import { PUBLIC_WEB_CONFIG } from "@/lib/public-config";

let firebaseApp: FirebaseApp | null = null;
let firebaseAuth: Auth | null = null;
let persistencePromise: Promise<void> | null = null;

export function isFirebaseAuthEnabled(): boolean {
  return PUBLIC_WEB_CONFIG.firebaseAuthEnabled && Boolean(PUBLIC_WEB_CONFIG.firebase);
}

function ensureFirebaseApp(): FirebaseApp {
  if (!isFirebaseAuthEnabled() || !PUBLIC_WEB_CONFIG.firebase) {
    throw new Error("Firebase authentication is not configured.");
  }

  if (firebaseApp) {
    return firebaseApp;
  }

  firebaseApp = getApps().length > 0 ? getApp() : initializeApp(PUBLIC_WEB_CONFIG.firebase);
  return firebaseApp;
}

export function getFirebaseAuth(): Auth {
  if (firebaseAuth) {
    return firebaseAuth;
  }

  firebaseAuth = getAuth(ensureFirebaseApp());
  return firebaseAuth;
}

export async function ensureFirebaseAuthPersistence(): Promise<void> {
  if (!isFirebaseAuthEnabled()) {
    return;
  }

  if (!persistencePromise) {
    persistencePromise = setPersistence(getFirebaseAuth(), browserLocalPersistence).catch((error: unknown) => {
      persistencePromise = null;
      throw error;
    });
  }

  await persistencePromise;
}
