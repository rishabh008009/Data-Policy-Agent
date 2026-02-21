/**
 * TypeScript interfaces matching backend models for the Data Policy Agent.
 */

// ============================================================================
// Enums
// ============================================================================

export const ViolationStatus = {
  PENDING: 'pending',
  CONFIRMED: 'confirmed',
  FALSE_POSITIVE: 'false_positive',
  RESOLVED: 'resolved',
} as const;
export type ViolationStatus = (typeof ViolationStatus)[keyof typeof ViolationStatus];

export const Severity = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical',
} as const;
export type Severity = (typeof Severity)[keyof typeof Severity];

export const PolicyStatus = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
} as const;
export type PolicyStatus = (typeof PolicyStatus)[keyof typeof PolicyStatus];

export const ScanStatus = {
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
} as const;
export type ScanStatus = (typeof ScanStatus)[keyof typeof ScanStatus];

export const ReviewActionType = {
  CONFIRM: 'confirm',
  FALSE_POSITIVE: 'false_positive',
  RESOLVE: 'resolve',
} as const;
export type ReviewActionType = (typeof ReviewActionType)[keyof typeof ReviewActionType];

// ============================================================================
// Policy Models
// ============================================================================

export interface Policy {
  id: string;
  filename: string;
  raw_text: string | null;
  uploaded_at: string;
  status: PolicyStatus;
  rules?: ComplianceRule[];
}

export interface PolicyResponse {
  id: string;
  filename: string;
  status: string;
  uploaded_at: string;
  rule_count: number;
}

export interface PolicyWithRules extends Policy {
  rules: ComplianceRule[];
}

// ============================================================================
// Compliance Rule Models
// ============================================================================

export interface ComplianceRule {
  id: string;
  policy_id: string;
  rule_code: string;
  description: string;
  evaluation_criteria: string;
  target_table: string | null;
  generated_sql: string | null;
  severity: Severity;
  is_active: boolean;
  created_at: string;
}

export interface ComplianceRuleResponse {
  id: string;
  policy_id: string;
  rule_code: string;
  description: string;
  evaluation_criteria: string;
  target_table: string | null;
  severity: Severity;
  is_active: boolean;
}

export interface RuleUpdateRequest {
  is_active?: boolean;
}

// ============================================================================
// Violation Models
// ============================================================================

export interface Violation {
  id: string;
  rule_id: string;
  record_identifier: string;
  record_data: Record<string, unknown>;
  justification: string;
  remediation_suggestion: string | null;
  severity: Severity;
  status: ViolationStatus;
  detected_at: string;
  resolved_at: string | null;
}

export interface ViolationResponse {
  id: string;
  rule_id: string;
  rule_code: string;
  rule_description: string;
  record_identifier: string;
  record_data: Record<string, unknown>;
  justification: string;
  remediation_suggestion: string | null;
  severity: Severity;
  status: ViolationStatus;
  detected_at: string;
}

export interface ViolationFilters {
  status?: ViolationStatus;
  severity?: Severity;
  rule_id?: string;
  start_date?: string;
  end_date?: string;
  skip?: number;
  limit?: number;
}

// ============================================================================
// Review Action Models
// ============================================================================

export interface ReviewAction {
  id: string;
  violation_id: string;
  action_type: ReviewActionType;
  reviewer_id: string;
  notes: string | null;
  created_at: string;
}

export interface ReviewDecision {
  action: ReviewActionType;
  notes?: string | null;
  reviewer_id?: string;
}

// ============================================================================
// Database Connection Models
// ============================================================================

export interface DatabaseConnection {
  id: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  is_active: boolean;
  created_at: string;
}

export interface DBConnectionConfig {
  host: string;
  port?: number;
  database: string;
  username: string;
  password: string;
}

export interface DatabaseSchema {
  tables: TableSchema[];
}

export interface TableSchema {
  name: string;
  columns: ColumnSchema[];
}

export interface ColumnSchema {
  name: string;
  data_type: string;
  is_nullable: boolean;
  is_primary_key: boolean;
}

// ============================================================================
// Scan Models
// ============================================================================

export interface ScanHistory {
  id: string;
  started_at: string;
  completed_at: string | null;
  status: ScanStatus;
  violations_found: number;
  new_violations: number;
  error_message: string | null;
}

export interface ScanResult {
  scan_id: string;
  started_at: string;
  completed_at: string;
  total_violations: number;
  new_violations: number;
  status: string;
}

export interface ScanRequest {
  rule_ids?: string[];
}

// ============================================================================
// Monitoring Models
// ============================================================================

export interface MonitoringConfig {
  id: string;
  interval_minutes: number;
  is_enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
}

export interface SchedulerStatus {
  is_enabled: boolean;
  interval_minutes: number;
  next_run_at: string | null;
  last_run_at: string | null;
  is_running: boolean;
}

export interface ScheduleConfig {
  interval_minutes: number;
}

// ============================================================================
// Dashboard Models
// ============================================================================

export interface DashboardSummary {
  total_violations: number;
  total_policies: number;
  total_rules: number;
  total_transactions: number;
  pending_count: number;
  confirmed_count: number;
  resolved_count: number;
  false_positive_count: number;
  by_severity: Record<Severity, number>;
  last_scan_at: string | null;
  next_scan_at: string | null;
}

export interface TrendDataPoint {
  date: string;
  total_violations: number;
  new_violations: number;
  resolved_violations: number;
}

export const TrendIndicator = {
  IMPROVEMENT: 'improvement',
  DEGRADATION: 'degradation',
  STABLE: 'stable',
} as const;
export type TrendIndicator = (typeof TrendIndicator)[keyof typeof TrendIndicator];

export interface TrendSummary {
  current_period_total: number;
  previous_period_total: number;
  percentage_change: number | null;
  trend_indicator: TrendIndicator;
  total_new_violations: number;
  total_resolved_violations: number;
}

export interface TrendData {
  time_range: string;
  bucket: string;
  data_points: TrendDataPoint[];
  summary: TrendSummary;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
  connection?: DatabaseConnection;
}
