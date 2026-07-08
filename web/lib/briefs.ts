// Starter briefs shown on a new project's empty intake, so first-run isn't a
// blank box. Clicking one pre-fills the composer; the user can edit before
// sending. Kept client-side — these are just seed prompts.

export interface TemplateBrief {
  id: string;
  label: string;
  prompt: string;
}

export const TEMPLATE_BRIEFS: TemplateBrief[] = [
  {
    id: "saas",
    label: "B2B SaaS",
    prompt:
      "Build a multi-tenant B2B SaaS with team workspaces, role-based access control, " +
      "subscription billing, and an admin dashboard. Expect a few thousand business customers.",
  },
  {
    id: "marketplace",
    label: "Marketplace",
    prompt:
      "Build a two-sided marketplace connecting service providers with customers: search, " +
      "booking, payments with escrow, reviews, and in-app messaging. Plan for one million users.",
  },
  {
    id: "mobile",
    label: "Mobile backend",
    prompt:
      "Design the backend for a consumer mobile app (iOS + Android): accounts and social login, " +
      "a REST API, push notifications, media uploads, and product analytics.",
  },
  {
    id: "ai",
    label: "AI / RAG app",
    prompt:
      "Build an AI product that answers questions over a company's documents using " +
      "retrieval-augmented generation: document ingestion, vector search, streaming chat, " +
      "and usage metering.",
  },
  {
    id: "internal",
    label: "Internal tool",
    prompt:
      "Build an internal operations tool for a mid-size company: dashboards, CRUD over business " +
      "data, role-based access, audit logging, and CSV import/export.",
  },
];
