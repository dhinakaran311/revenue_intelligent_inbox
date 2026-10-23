export interface PersonRow {
  person: string
  records: number
  with_text: number
  needs_attention: number
  connected_source_reported: number
  connection_known: number
}

export interface AttentionItem {
  record_ref: string
  source_type: string
  source_id: string
  person_name: string | null
  headline: string | null
  priority: string | null
  review_state: string
  effective_route_ids: string[]
  has_manual_route: boolean
}

export interface DashboardMetrics {
  filters: { source_type: string | null; person: string | null }
  people: { call_reps: string[]; meeting_organisers: string[] }
  totals: { records: number; calls: number; meetings: number }
  activity_by_day: Array<{ date: string; calls: number; meetings: number; total: number }>
  activity_by_hour: Array<{ hour: string; calls: number; meetings: number }>
  call_reps: PersonRow[]
  meeting_organisers: PersonRow[]
  text_coverage: {
    usable: number
    total: number
    pct: number | null
    calls: { usable: number; total: number }
    meetings: { usable: number; total: number }
    no_text_reasons: Array<{ reason: string; count: number }>
  }
  connection: { connected: number; known: number; unknown: number; pct: number | null }
  review_states: Record<string, number>
  freshness: Record<string, number>
  manual_overrides: number
  routes: Array<{ route_id: string; label: string; definition: string; records: number }>
  route_assignments: number
  routed_records: number
  label_conflicts: Array<{ record_ref: string; source_type: string; source_id: string; source_label: string | null }>
  attention: AttentionItem[]
  definitions: Array<{ key: string; label: string; definition: string }>
}

export interface RecordRow {
  source_type: string
  source_id: string
  record_ref: string | null
  revision: number
  activity_date: string | null
  activity_at: string | null
  person_name: string | null
  person_role: string | null
  title: string | null
  has_usable_text: boolean
  text_status: string
  source_label: string | null
  is_connected: boolean | null
  intake_state: string
  analysis_state: string
  analysis_source: string | null
  analysis_revision: number | null
  has_manual_route: boolean
  manual_route_id: string | null
  suggested_route_ids: string[]
  effective_route_ids: string[]
  review_state: string
  priority: string | null
  headline: string | null
  label_agrees: boolean | null
}

export interface SuggestedRoute {
  route_id: string
  label: string
  rationale: string | null
  evidence_ref: string | null
  priority: string | null
  output: string | null
  owner: string | null
  is_manual: boolean
}

export interface EvidenceRef {
  id: string
  turn: number | null
  quote: string
  supports: string
}

export interface Analysis {
  analysis_id: string
  headline: string | null
  priority: string | null
  suggested_routes: SuggestedRoute[]
  evidence: EvidenceRef[]
  concise_output: string | null
  what_established: string | null
  what_not_established: string | null
  next_action: string | null
  owner: string | null
  confidence: string | null
  uncertainty: string | null
  label_check: string | null
  label_agrees: boolean | null
  analysis_source: string | null
  source_revision: number | null
  freshness_label: string | null
  created_at: string | null
}

export interface ManualRoute {
  route_id: string
  rationale: string | null
  author: string | null
  is_active: boolean
  created_at: string | null
  reset_at?: string | null
}

export interface RecordDetail extends RecordRow {
  source_payload: Record<string, unknown> | null
  transcript_payload: Record<string, unknown> | null
  current_analysis: Analysis | null
  stale_analysis: Analysis | null
  manual_route: ManualRoute | null
  manual_route_history: ManualRoute[]
}

export interface Turn {
  turn_number: number
  speaker: string | null
  timecode: string | null
  text: string
}

export interface Evidence {
  found: boolean
  has_usable_text: boolean
  transcript: string | null
  turns: Turn[]
  evidence: Array<EvidenceRef & { offset?: number; turn_number?: number | null }>
  text_status?: string
}

export interface ExportRun {
  id: string
  is_current: boolean
  bundle_path: string
  manifest_path: string
  created_at: string | null
}

export interface BriefRef {
  record_ref: string
  cite?: string
  quote?: string
}

export interface BriefRecordState {
  source_type: string
  source_id: string
  imported: boolean
  revision?: number
  review_state?: string
  analysis_state?: string
  has_manual_route?: boolean
  manual_route_id?: string | null
  effective_route_ids?: string[]
}

export interface Brief {
  date: string
  timezone: string
  basis: string
  summary: string
  priorities: Array<{ rank: number; title: string; why: string; action: string; owner: string; refs: BriefRef[] }>
  follow_ups: Array<{ record_ref: string; owner: string; action: string; cite: string }>
  coaching: Array<{ theme: string; detail: string; refs: BriefRef[] }>
  product_signals: Array<{ signal: string; detail: string; refs: BriefRef[] }>
  data_quality: Array<{ issue: string; detail: string; refs: BriefRef[] }>
  not_established: string[]
  records: Record<string, BriefRecordState>
  activity: {
    totals: DashboardMetrics["totals"]
    text_coverage: DashboardMetrics["text_coverage"]
    call_reps: PersonRow[]
    meeting_organisers: PersonRow[]
    connection: DashboardMetrics["connection"]
  }
}

export interface ImportRun {
  id: string
  filename: string | null
  received_at: string
  total_records: number | null
  accepted: number | null
  ignored: number | null
  replaced: number | null
  error_count: number
}
