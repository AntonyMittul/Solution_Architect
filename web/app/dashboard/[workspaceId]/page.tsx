"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Banner, Button, ErrorText, Field, Spinner, TextInput } from "@/components/ui";
import { useMe } from "@/features/auth/use-auth";
import {
  useCreateProject,
  useDeleteProject,
  useProjects,
  useRestoreProject,
} from "@/features/projects/use-projects";
import { useWorkspaces } from "@/features/workspaces/use-workspaces";
import { canWriteProjects } from "@/lib/types";

export default function ProjectsPage() {
  const workspaceId = useParams<{ workspaceId: string }>().workspaceId;
  const { data: me } = useMe();
  const { data: workspaces } = useWorkspaces();
  const projects = useProjects(workspaceId);
  const createProject = useCreateProject(workspaceId);
  const deleteProject = useDeleteProject(workspaceId);
  const restoreProject = useRestoreProject(workspaceId);

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [lastDeleted, setLastDeleted] = useState<{ id: string; name: string } | null>(null);

  const workspace = workspaces?.find((w) => w.id === workspaceId);
  const canWrite = workspace ? canWriteProjects(workspace.role) : false;
  const verified = me?.email_verified ?? true;

  function onCreate(event: React.FormEvent) {
    event.preventDefault();
    createProject.mutate(
      { name, description: description || undefined },
      {
        onSuccess: () => {
          setName("");
          setDescription("");
          setShowForm(false);
        },
      },
    );
  }

  function onDelete(project: { id: string; name: string }) {
    deleteProject.mutate(project.id, {
      onSuccess: () => setLastDeleted(project),
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Projects</h2>
          {workspace && <p className="text-sm text-slate-500">{workspace.name}</p>}
        </div>
        {canWrite && verified && !showForm && (
          <Button onClick={() => setShowForm(true)}>New project</Button>
        )}
      </div>

      {!verified && (
        <Banner tone="amber">
          Verify your email address to create projects. Check your inbox for the link.
        </Banner>
      )}

      {lastDeleted && (
        <Banner tone="slate">
          <span>Deleted “{lastDeleted.name}”.</span>
          <button
            onClick={() =>
              restoreProject.mutate(lastDeleted.id, { onSuccess: () => setLastDeleted(null) })
            }
            className="font-medium text-indigo-400 hover:text-indigo-300"
          >
            Undo
          </button>
          <button
            onClick={() => setLastDeleted(null)}
            className="ml-auto text-slate-500 hover:text-slate-300"
          >
            Dismiss
          </button>
        </Banner>
      )}

      {showForm && (
        <form
          onSubmit={onCreate}
          className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/50 p-5"
        >
          <Field label="Project name">
            <TextInput
              required
              autoFocus
              placeholder="Food delivery app for one million users"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field label="Description (optional)">
            <TextInput value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          {createProject.isError && (
            <ErrorText>{(createProject.error as Error).message}</ErrorText>
          )}
          <div className="flex gap-2">
            <Button type="submit" disabled={createProject.isPending}>
              {createProject.isPending ? "Creating…" : "Create project"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      {projects.isLoading && <Spinner />}
      {projects.isError && <ErrorText>{(projects.error as Error).message}</ErrorText>}

      {projects.data && projects.data.length === 0 && !showForm && (
        <div className="rounded-xl border border-dashed border-slate-800 py-16 text-center text-sm text-slate-500">
          No projects yet.
          {canWrite && verified && " Create your first one to get started."}
        </div>
      )}

      <ul className="space-y-2">
        {projects.data?.map((project) => (
          <li
            key={project.id}
            className="flex items-center gap-4 rounded-xl border border-slate-800 bg-slate-900/50 px-5 py-4"
          >
            <Link
              href={`/dashboard/${workspaceId}/projects/${project.id}`}
              className="min-w-0 flex-1 hover:opacity-80"
            >
              <p className="truncate font-medium">{project.name}</p>
              {project.description && (
                <p className="truncate text-sm text-slate-500">{project.description}</p>
              )}
            </Link>
            <span className="ml-auto rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
              {project.status}
            </span>
            {canWrite && (
              <Button variant="danger" onClick={() => onDelete(project)}>
                Delete
              </Button>
            )}
          </li>
        ))}
      </ul>

      <p className="pt-4 text-xs text-slate-600">
        Blueprint generation arrives in the next milestone.{" "}
        <Link href="/playground" className="text-slate-500 hover:text-slate-300">
          Try the run streaming playground →
        </Link>
      </p>
    </div>
  );
}
