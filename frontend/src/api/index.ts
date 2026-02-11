/**
 * API module - Re-exports all API functions and types.
 */

// Export the axios client
export { default as apiClient, buildQueryParams, handleApiResponse } from './client';

// Export all types
export * from './types';

// Export policy API functions
export {
  deletePolicy,
  getPolicy,
  getPolicies,
  policiesApi,
  uploadPolicy,
} from './policies';

// Export rules API functions
export {
  disableRule,
  enableRule,
  getRule,
  getRules,
  rulesApi,
  updateRule,
} from './rules';

// Export database API functions
export {
  connectDatabase,
  databaseApi,
  getActiveConnection,
  getDatabaseSchema,
  triggerScan,
} from './database';

// Export violations API functions
export {
  confirmViolation,
  getAllViolations,
  getViolation,
  getViolations,
  markFalsePositive,
  resolveViolation,
  reviewViolation,
  violationsApi,
} from './violations';

// Export monitoring API functions
export {
  configureSchedule,
  disableSchedule,
  enableSchedule,
  getMonitoringStatus,
  monitoringApi,
} from './monitoring';

// Export dashboard API functions
export {
  dashboardApi,
  getDashboardSummary,
  getTrendDataPoints,
  getViolationTrends,
} from './dashboard';
export type { TimeRange, TrendBucket } from './dashboard';

// Import for consolidated API object
import { policiesApi } from './policies';
import { rulesApi } from './rules';
import { databaseApi } from './database';
import { violationsApi } from './violations';
import { monitoringApi } from './monitoring';
import { dashboardApi } from './dashboard';

// Consolidated API object for convenient access
export const api = {
  policies: policiesApi,
  rules: rulesApi,
  database: databaseApi,
  violations: violationsApi,
  monitoring: monitoringApi,
  dashboard: dashboardApi,
};
