"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Banner } from "@/components/ui";
import { useResendVerification, useVerifyEmail } from "@/features/auth/use-auth";

/**
 * Unverified-email banner with a working recovery path. In dev the resend
 * endpoint returns the token (no SMTP), so we complete verification in-app and
 * refresh the session; in production it triggers a real email.
 */
export function VerifyEmailBanner({ message }: { message: string }) {
  const qc = useQueryClient();
  const resend = useResendVerification();
  const verify = useVerifyEmail();
  const [sent, setSent] = useState(false);
  const busy = resend.isPending || verify.isPending;

  async function onClick() {
    const result = await resend.mutateAsync();
    if (result.verification_token) {
      await verify.mutateAsync(result.verification_token); // dev: finish in-app
      await qc.invalidateQueries({ queryKey: ["me"] }); // banner disappears on refetch
    } else {
      setSent(true);
    }
  }

  return (
    <Banner tone="amber">
      <span>{sent ? "Verification email sent — check your inbox." : message}</span>
      {!sent && (
        <button
          onClick={() => void onClick()}
          disabled={busy}
          className="ml-auto rounded-lg border border-amber-800 px-3 py-1 text-xs font-medium text-amber-100 hover:bg-amber-900/40 disabled:opacity-60"
        >
          {busy ? "Verifying…" : "Resend / verify"}
        </button>
      )}
    </Banner>
  );
}
