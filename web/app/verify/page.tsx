"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";

import { AuthCard, Button, ErrorText, Spinner } from "@/components/ui";
import { useVerifyEmail } from "@/features/auth/use-auth";

function VerifyInner() {
  const token = useSearchParams().get("token");
  const verify = useVerifyEmail();
  const attempted = useRef(false);

  useEffect(() => {
    if (token && !attempted.current) {
      attempted.current = true;
      verify.mutate(token);
    }
  }, [token, verify]);

  if (!token) {
    return (
      <AuthCard title="Invalid link">
        <ErrorText>This verification link is missing its token.</ErrorText>
      </AuthCard>
    );
  }

  if (verify.isSuccess) {
    return (
      <AuthCard title="Email verified" subtitle="Your account is ready.">
        <Link
          href="/login"
          className="block rounded-lg bg-indigo-600 px-4 py-2 text-center text-sm font-medium text-white hover:bg-indigo-500"
        >
          Continue to sign in
        </Link>
      </AuthCard>
    );
  }

  if (verify.isError) {
    return (
      <AuthCard title="Verification failed">
        <ErrorText>{(verify.error as Error).message}</ErrorText>
        <Button variant="ghost" className="mt-4 w-full" onClick={() => verify.mutate(token)}>
          Try again
        </Button>
      </AuthCard>
    );
  }

  return <Spinner label="Verifying your email…" />;
}

export default function VerifyPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <VerifyInner />
    </Suspense>
  );
}
