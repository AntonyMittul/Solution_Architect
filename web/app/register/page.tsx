"use client";

import Link from "next/link";
import { useState } from "react";

import { AuthCard, Button, ErrorText, Field, TextInput } from "@/components/ui";
import { useRegister } from "@/features/auth/use-auth";
import type { RegisterResponse } from "@/lib/types";

export default function RegisterPage() {
  const register = useRegister();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [result, setResult] = useState<RegisterResponse | null>(null);

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    register.mutate({ name, email, password }, { onSuccess: setResult });
  }

  if (result) {
    // Prod: a verification link is emailed. Dev: the API returns the token so
    // the link can be followed here directly.
    const devLink = result.verification_token
      ? `/verify?token=${encodeURIComponent(result.verification_token)}`
      : null;
    return (
      <AuthCard title="Check your email" subtitle={`We sent a verification link to ${email}.`}>
        <p className="text-sm text-slate-400">
          Verify your address to unlock project creation, then sign in.
        </p>
        {devLink && (
          <Link
            href={devLink}
            className="mt-4 block rounded-lg border border-slate-700 px-4 py-2 text-center text-sm text-indigo-300 hover:bg-slate-800"
          >
            Verify now (dev)
          </Link>
        )}
        <Link
          href="/login"
          className="mt-3 block text-center text-sm text-slate-400 hover:text-slate-200"
        >
          Continue to sign in
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Create your account" subtitle="Start architecting in minutes.">
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Name">
          <TextInput
            autoComplete="name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
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
            autoComplete="new-password"
            required
            minLength={10}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <p className="text-xs text-slate-500">At least 10 characters.</p>
        {register.isError && <ErrorText>{(register.error as Error).message}</ErrorText>}
        <Button type="submit" disabled={register.isPending} className="w-full">
          {register.isPending ? "Creating…" : "Create account"}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-400">
        Already have an account?{" "}
        <Link href="/login" className="text-indigo-400 hover:text-indigo-300">
          Sign in
        </Link>
      </p>
    </AuthCard>
  );
}
