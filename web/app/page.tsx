"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Spinner } from "@/components/ui";
import { useMe } from "@/features/auth/use-auth";

export default function Home() {
  const router = useRouter();
  const { data, isLoading, isError } = useMe();

  useEffect(() => {
    if (isLoading) return;
    router.replace(isError || !data ? "/login" : "/dashboard");
  }, [data, isError, isLoading, router]);

  return <Spinner label="Starting…" />;
}
