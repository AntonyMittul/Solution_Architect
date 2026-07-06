"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthCard, Button, ErrorText, Field, TextInput } from "@/components/ui";
import { useLogin } from "@/features/auth/use-auth";

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    login.mutate({ email, password }, { onSuccess: () => router.replace("/dashboard") });
  }

  return (
    <AuthCard title="Sign in" subtitle="Welcome back to AI Solution Architect.">
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Email">
          <TextInput
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field label="Password">
          <TextInput
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        {login.isError && <ErrorText>{(login.error as Error).message}</ErrorText>}
        <Button type="submit" disabled={login.isPending} className="w-full">
          {login.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-400">
        No account?{" "}
        <Link href="/register" className="text-indigo-400 hover:text-indigo-300">
          Create one
        </Link>
      </p>
    </AuthCard>
  );
}
