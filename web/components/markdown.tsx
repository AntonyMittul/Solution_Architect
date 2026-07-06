"use client";

import ReactMarkdown, { type Components } from "react-markdown";

const components: Components = {
  h1: (props) => <h1 className="mb-2 mt-4 text-lg font-semibold text-slate-100" {...props} />,
  h2: (props) => <h2 className="mb-2 mt-4 text-base font-semibold text-slate-100" {...props} />,
  h3: (props) => <h3 className="mb-1 mt-3 font-semibold text-slate-200" {...props} />,
  p: (props) => <p className="my-2 text-sm leading-relaxed text-slate-300" {...props} />,
  ul: (props) => <ul className="my-2 ml-5 list-disc text-sm text-slate-300" {...props} />,
  ol: (props) => <ol className="my-2 ml-5 list-decimal text-sm text-slate-300" {...props} />,
  li: (props) => <li className="my-0.5" {...props} />,
  strong: (props) => <strong className="font-semibold text-slate-100" {...props} />,
  code: (props) => <code className="rounded bg-slate-800 px-1 py-0.5 text-xs" {...props} />,
  a: (props) => <a className="text-indigo-400 hover:text-indigo-300" {...props} />,
};

export function MarkdownView({ text }: { text: string }) {
  return <ReactMarkdown components={components}>{text}</ReactMarkdown>;
}
