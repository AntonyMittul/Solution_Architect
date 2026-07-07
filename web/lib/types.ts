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

export type ArtifactType =
  | "architecture_doc"
  | "tech_stack"
  | "api_spec"
  | "db_schema"
  | "diagram"
  | "cost_estimate"
  | "design_doc";

export interface Provenance {
  run_id: string;
  agent: string;
  model: string;
  source: string;
  requirements_version: number;
}

export interface ArtifactVersionData {
  version: number;
  content: Record<string, unknown>;
  provenance: Provenance;
  created_at: string;
}

export interface ArtifactSummary {
  type: ArtifactType;
  is_stale: boolean;
  latest: ArtifactVersionData | null;
}

export interface StartBlueprintResponse {
  run_id: string;
  status: string;
}

// Artifact content shapes (the viewers narrow `content` to these).
export interface ArchitectureContent {
  overview: string;
  components: { name: string; type: string; responsibility: string }[];
  data_flows: string[];
  key_decisions: { decision: string; rationale: string }[];
}
export interface TechStackContent {
  choices: { layer: string; choice: string; alternatives: string[]; rationale: string }[];
}
export interface ApiSpecContent {
  title: string;
  version: string;
  endpoints: { method: string; path: string; summary: string }[];
}
export interface DbSchemaContent {
  tables: {
    name: string;
    columns: { name: string; type: string; nullable: boolean }[];
    primary_key: string[];
  }[];
}
export interface DiagramContent {
  nodes: { id: string; label: string; type: string }[];
  edges: { source: string; target: string; label: string }[];
}
export interface CostContent {
  currency: string;
  line_items: {
    service: string;
    monthly_low: number;
    monthly_expected: number;
    monthly_high: number;
    notes: string;
  }[];
  pricing_note: string;
}
export interface DesignDocContent {
  markdown: string;
}

export interface Usage {
  plan: string;
  period_start: string;
  runs_this_month: number;
  monthly_run_quota: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  per_run_token_budget: number;
}

const WRITE_ROLES: ReadonlySet<Role> = new Set<Role>(["owner", "admin", "member"]);
const MANAGE_ROLES: ReadonlySet<Role> = new Set<Role>(["owner", "admin"]);

export const canWriteProjects = (role: Role): boolean => WRITE_ROLES.has(role);
export const canManageMembers = (role: Role): boolean => MANAGE_ROLES.has(role);
