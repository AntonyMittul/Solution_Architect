"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Banner, Spinner } from "@/components/ui";
import { useWorkspaces } from "@/features/workspaces/use-workspaces";

export default function DashboardIndex() {
  const router = useRouter();
  const { data: workspaces, isLoading } = useWorkspaces();

  useEffect(() => {
    if (workspaces && workspaces.length > 0) {
      router.replace(`/dashboard/${workspaces[0].id}`);
    }
  }, [workspaces, router]);

  if (isLoading || (workspaces && workspaces.length > 0)) {
    return <Spinner label="Opening your workspace…" />;
  }
  return <Banner tone="slate">No workspaces found for your account.</Banner>;
}
