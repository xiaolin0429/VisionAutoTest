export interface ApiMeta {
  request_id: string
}

export interface PaginationMeta extends ApiMeta {
  page: number
  page_size: number
  total: number
}

export interface ApiEnvelope<T> {
  data: T
  meta: ApiMeta
}

export interface PaginatedEnvelope<T> {
  data: T[]
  meta: PaginationMeta
}

export interface SessionResponseDTO {
  session_id: string
  access_token: string
  refresh_token: string
  expires_in: number
  user: {
    id: number
    username: string
    display_name: string
  }
}

export interface WorkspaceReadDTO {
  id: number
  workspace_code: string
  workspace_name: string
  description: string | null
  status: string
  owner_user_id: number
  created_at: string
  updated_at: string
}

export interface WorkspaceMemberReadDTO {
  id: number
  workspace_id: number
  user_id: number
  workspace_role: string
  status: string
  joined_at: string
  created_at: string
}

export interface EnvironmentProfileReadDTO {
  id: number
  workspace_id: number
  profile_name: string
  base_url: string
  description: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface EnvironmentVariableReadDTO {
  id: number
  environment_profile_id: number
  var_key: string
  is_secret: boolean
  description: string | null
  created_at: string
  updated_at: string
  display_value: string | null
}

export interface DeviceProfileReadDTO {
  id: number
  workspace_id: number
  profile_name: string
  device_type: string
  viewport_width: number
  viewport_height: number
  device_scale_factor: number
  user_agent: string | null
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface TemplateReadDTO {
  id: number
  workspace_id: number
  template_code: string
  template_name: string
  template_type: string
  match_strategy: string
  threshold_value: number
  status: string
  current_baseline_revision_id: number | null
  created_at: string
  updated_at: string
}

export interface BaselineRevisionReadDTO {
  id: number
  template_id: number
  revision_no: number
  media_object_id: number
  source_type: string
  is_current: boolean
  remark: string | null
  created_at: string
}

export interface MaskRegionReadDTO {
  id: number
  template_id: number
  region_name: string
  x_ratio: number
  y_ratio: number
  width_ratio: number
  height_ratio: number
  sort_order: number
  created_at: string
  updated_at: string
}

export interface TestCaseReadDTO {
  id: number
  workspace_id: number
  case_code: string
  case_name: string
  status: string
  priority: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface TestCaseStepDTO {
  id: number
  test_case_id: number
  step_no: number
  step_type: string
  step_name: string
  component_id: number | null
  template_id: number | null
  payload_json: Record<string, unknown>
  timeout_ms: number
  retry_times: number
  created_at: string
  updated_at: string
}

export interface TestSuiteReadDTO {
  id: number
  workspace_id: number
  suite_code: string
  suite_name: string
  status: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface SuiteCaseDTO {
  id: number
  test_suite_id: number
  test_case_id: number
  sort_order: number
  created_at: string
}

export interface TestRunReadDTO {
  id: number
  workspace_id: number
  test_suite_id: number
  environment_profile_id: number
  device_profile_id: number | null
  trigger_source: string
  triggered_by: number | null
  idempotency_key: string | null
  status: string
  started_at: string | null
  finished_at: string | null
  total_case_count: number
  passed_case_count: number
  failed_case_count: number
  error_case_count: number
  created_at: string
  updated_at: string
}

export interface TestCaseRunReadDTO {
  id: number
  test_run_id: number
  test_case_id: number
  sort_order: number
  status: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  failure_reason_code: string | null
  failure_summary: string | null
  created_at: string
}

export interface StepResultReadDTO {
  id: number
  case_run_id: number
  step_no: number
  step_type: string
  status: string
  score_value: number | null
  expected_media_object_id: number | null
  actual_media_object_id: number | null
  diff_media_object_id: number | null
  error_message: string | null
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  created_at: string
}

export interface RunReportReadDTO {
  id: number
  test_run_id: number
  summary_status: string
  summary_json: Record<string, unknown>
  generated_at: string
  created_at: string
}
