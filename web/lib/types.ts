// M1: hand-written to mirror the backend response schemas. These are slated to
// be replaced by types generated from the backend OpenAPI spec (a CI job) so
// there are no hand-maintained fetch types — kept in one file to make that swap
// mechanical.

export interface Problem {
  type: string;
  title: string;
  status: number;
  detail: string | null;
  instance: string;
  trace_id: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  email_verified: boolean;
  created_at: string;
}

export type Role = "owner" | "admin" | "member" | "viewer";

export interface Workspace {
  id: string;
  slug: string;
  name: string;
  kind: "personal" | "team";
  plan: string;
  role: Role;
}

export interface Member {
  user_id: string;
  email: string;
  name: string;
  role: Role;
}

export type ProjectStatus = "active" | "archived";

export interface Project {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  settings: Record<string, unknown>;
  created_by: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface RegisterResponse {
  user: User;
  workspace_id: string;
  verification_token: string | null;
}

export interface ClarifyingQuestion {
  id: string;
  question: string;
  why: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: { text?: string; questions?: ClarifyingQuestion[] };
  run_id: string | null;
  created_at: string;
}

export interface RequirementsContent {
  schema_version: number;
  summary: string;
  goals: string[];
  actors: string[];
  functional_requirements: string[];
  non_functional_requirements: string[];
  constraints: string[];
  assumptions: string[];
  open_questions: string[];
}

export interface Requirements {
  version: number;
  status: "draft" | "confirmed";
  content: RequirementsContent;
  created_by: string;
  created_at: string;
}

export interface PostMessageResult {
  thread_id: string;
  run_id: string;
  resumed: boolean;
}

const WRITE_ROLES: ReadonlySet<Role> = new Set<Role>(["owner", "admin", "member"]);
const MANAGE_ROLES: ReadonlySet<Role> = new Set<Role>(["owner", "admin"]);

export const canWriteProjects = (role: Role): boolean => WRITE_ROLES.has(role);
export const canManageMembers = (role: Role): boolean => MANAGE_ROLES.has(role);
