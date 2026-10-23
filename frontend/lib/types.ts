export interface DashboardMetrics {
  text_coverage: {
    total: number
    usable: number
    pct: number
  }
  activity_by_person: {
    calls_total: number
    meetings_total: number
    by_person: Array<{
      person_name: string
      person_role: string
      calls: number
      meetings: number
    }>
  }
  route_summary: Array<{
    route_state: string
    count: number
  }>
  analysis_state_counts: Array<{
    analysis_state: string
    count: number
  }>
  definitions: Record<string, string>
}

export interface RecordRow {
  source_type: string
  source_id: string
  record_ref: string | null
  revision: number
  activity_date: string | null
  person_name: string | null
  person_role: string | null
  has_usable_text: boolean
  intake_state: string
  analysis_state: string
  analysis_source: string | null
  has_manual_route: boolean
  route_state: string
}

export interface SuggestedRoute {
  route_id: string
  label: string
  rationale: string | null
  evidence_ref: string | null
  is_manual: boolean
}

export interface Analysis {
  analysis_id: string
  suggested_routes: SuggestedRoute[]
  concise_output: string | null
  what_established: string | null
  what_not_established: string | null
  next_action: string | null
  owner: string | null
  confidence: string | null
  uncertainty: string | null
  analysis_source: string | null
  source_revision: number | null
  freshness_label: string | null
}

export interface EvidenceItem {
  ref: string | null
  type: string
  quote: string | null
  turn_number?: number | null
  speaker?: string | null
}

export interface Evidence {
  found: boolean
  has_usable_text: boolean
  evidence: EvidenceItem[]
}

export interface ManualRoute {
  route_id: string
  rationale: string | null
  author: string | null
  is_active: boolean
  created_at: string | null
}

export interface RecordDetail extends RecordRow {
  source_payload: Record<string, unknown> | null
  transcript_payload: Record<string, unknown> | null
  current_analysis: Analysis | null
  manual_route: ManualRoute | null
}

export interface ExportRun {
  id: string
  is_current: boolean
  bundle_path: string
  manifest_path: string
  created_at: string | null
}
