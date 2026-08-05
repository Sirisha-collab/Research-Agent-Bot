export interface Health {
  status: string;
  llm_provider: string;
  llm_model: string;
  api_key_configured: boolean;
  embedding_model: string;
  indexed_documents: number;
  indexed_chunks: number;
}

export interface DocumentSummary {
  doc_id: string;
  title: string;
  authors: string;
  filename: string;
  page_count: number;
  n_chunks: number;
  n_tables: number;
  n_figures: number;
  ingested_at: string;
}

export interface Finding {
  finding: string;
  evidence: string;
  section: string;
}

export interface Metric {
  name: string;
  value: string;
  context: string;
}

export interface Findings {
  findings?: Finding[];
  contributions?: string[];
  limitations?: string[];
  future_work?: string[];
  methods?: string[];
  metrics?: Metric[];
}

export interface TableBlock {
  id: string;
  page: number;
  flavour: string;
  accuracy: number;
  n_rows: number;
  n_cols: number;
  markdown: string;
  caption: string;
}

export interface FigureBlock {
  id: string;
  page: number;
  path: string;
  caption: string;
  width: number;
  height: number;
}

export interface SectionBlock {
  title: string;
  canonical: string;
  page_start: number;
  words: number;
}

export interface DocumentDetail {
  doc_id: string;
  title: string;
  authors: string;
  filename?: string;
  ingested_at?: string;
  page_count: number;
  n_chunks: number;
  summary: string;
  explanation: string;
  findings: Findings;
  followups: string[];
  tables: TableBlock[];
  figures: FigureBlock[];
  sections: SectionBlock[];
  warnings: string[];
  elapsed_s: number;
}

export interface Source {
  label: string;
  doc_id: string;
  doc_title: string;
  section: string;
  page: number;
  score: number;
  snippet: string;
  full_text: string;
  kind: string;
}

export interface AskResponse {
  question: string;
  answer: string;
  sources: Source[];
  queries_used: string[];
  retrieval_rounds: number;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  rounds?: number;
}
