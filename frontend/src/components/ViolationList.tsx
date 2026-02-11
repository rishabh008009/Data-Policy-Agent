/**
 * ViolationList Component
 *
 * Displays a filterable table of compliance violations with severity indicators,
 * status badges, and filtering controls.
 *
 * Requirements: 6.5 - Filtering options by violation status, severity, rule, and date range
 */

import { useCallback, useEffect, useState } from 'react';
import { getViolations } from '../api/violations';
import type {
  PaginatedResponse,
  Severity,
  ViolationFilters,
  ViolationResponse,
  ViolationStatus,
} from '../api/types';

// ============================================================================
// Types
// ============================================================================

interface ViolationListProps {
  /** Callback when a violation row is clicked */
  onSelectViolation?: (violation: ViolationResponse) => void;
  /** Currently selected violation ID */
  selectedViolationId?: string;
  /** Initial filters to apply */
  initialFilters?: ViolationFilters;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get severity color classes for styling
 */
function getSeverityColors(severity: Severity): { bg: string; text: string; dot: string } {
  switch (severity) {
    case 'critical':
      return { bg: 'bg-red-100', text: 'text-red-800', dot: 'bg-red-500' };
    case 'high':
      return { bg: 'bg-orange-100', text: 'text-orange-800', dot: 'bg-orange-500' };
    case 'medium':
      return { bg: 'bg-yellow-100', text: 'text-yellow-800', dot: 'bg-yellow-500' };
    case 'low':
      return { bg: 'bg-green-100', text: 'text-green-800', dot: 'bg-green-500' };
    default:
      return { bg: 'bg-gray-100', text: 'text-gray-800', dot: 'bg-gray-500' };
  }
}

/**
 * Get status badge color classes
 */
function getStatusColors(status: ViolationStatus): { bg: string; text: string } {
  switch (status) {
    case 'pending':
      return { bg: 'bg-yellow-100', text: 'text-yellow-800' };
    case 'confirmed':
      return { bg: 'bg-red-100', text: 'text-red-800' };
    case 'false_positive':
      return { bg: 'bg-gray-100', text: 'text-gray-800' };
    case 'resolved':
      return { bg: 'bg-green-100', text: 'text-green-800' };
    default:
      return { bg: 'bg-gray-100', text: 'text-gray-800' };
  }
}

/**
 * Format status for display
 */
function formatStatus(status: ViolationStatus): string {
  switch (status) {
    case 'pending':
      return 'Pending';
    case 'confirmed':
      return 'Confirmed';
    case 'false_positive':
      return 'False Positive';
    case 'resolved':
      return 'Resolved';
    default:
      return status;
  }
}

/**
 * Format date for display
 */
function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return 'Invalid date';
  }
}

/**
 * Format date for input field (YYYY-MM-DD)
 */
function formatDateForInput(dateString: string | undefined): string {
  if (!dateString) return '';
  try {
    const date = new Date(dateString);
    return date.toISOString().split('T')[0];
  } catch {
    return '';
  }
}

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Severity indicator with colored dot
 */
function SeverityIndicator({ severity }: { severity: Severity }) {
  const colors = getSeverityColors(severity);
  return (
    <div className="flex items-center gap-2">
      <span className={`w-2.5 h-2.5 rounded-full ${colors.dot}`} />
      <span className={`text-sm font-medium capitalize ${colors.text}`}>{severity}</span>
    </div>
  );
}

/**
 * Status badge component
 */
function StatusBadge({ status }: { status: ViolationStatus }) {
  const colors = getStatusColors(status);
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}
    >
      {formatStatus(status)}
    </span>
  );
}

/**
 * Loading skeleton for table rows
 */
function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex items-center gap-4 p-4 border-b border-gray-200">
          <div className="w-3 h-3 bg-gray-200 rounded-full" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-gray-200 rounded w-24" />
            <div className="h-3 bg-gray-200 rounded w-48" />
          </div>
          <div className="h-6 bg-gray-200 rounded w-20" />
          <div className="h-4 bg-gray-200 rounded w-24" />
        </div>
      ))}
    </div>
  );
}

/**
 * Empty state component
 */
function EmptyState({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div className="text-center py-12">
      <svg
        className="mx-auto h-12 w-12 text-gray-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <h3 className="mt-4 text-lg font-medium text-gray-900">
        {hasFilters ? 'No Matching Violations' : 'No Violations Found'}
      </h3>
      <p className="mt-2 text-gray-500">
        {hasFilters
          ? 'Try adjusting your filters to see more results.'
          : 'Run a compliance scan to detect violations in your database.'}
      </p>
    </div>
  );
}

/**
 * Error display component
 */
function ErrorDisplay({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="text-center py-12">
      <svg
        className="mx-auto h-12 w-12 text-red-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
        />
      </svg>
      <h3 className="mt-4 text-lg font-medium text-red-800">Failed to Load Violations</h3>
      <p className="mt-2 text-red-600">{message}</p>
      <button
        onClick={onRetry}
        className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
      >
        Try Again
      </button>
    </div>
  );
}

/**
 * View details icon
 */
const ViewIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
    />
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
    />
  </svg>
);

// ============================================================================
// Filter Bar Component
// ============================================================================

interface FilterBarProps {
  filters: ViolationFilters;
  onFilterChange: (filters: ViolationFilters) => void;
  onClearFilters: () => void;
}

function FilterBar({ filters, onFilterChange, onClearFilters }: FilterBarProps) {
  const hasActiveFilters = Boolean(
    filters.status || filters.severity || filters.rule_id || filters.start_date || filters.end_date
  );

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex flex-wrap gap-4 items-end">
        {/* Status Filter */}
        <div className="flex flex-col">
          <label htmlFor="status-filter" className="text-sm font-medium text-gray-700 mb-1">
            Status
          </label>
          <select
            id="status-filter"
            value={filters.status || ''}
            onChange={(e) =>
              onFilterChange({
                ...filters,
                status: (e.target.value as ViolationStatus) || undefined,
              })
            }
            className="px-3 py-2 border border-gray-300 rounded-lg text-gray-700 bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="confirmed">Confirmed</option>
            <option value="false_positive">False Positive</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>

        {/* Severity Filter */}
        <div className="flex flex-col">
          <label htmlFor="severity-filter" className="text-sm font-medium text-gray-700 mb-1">
            Severity
          </label>
          <select
            id="severity-filter"
            value={filters.severity || ''}
            onChange={(e) =>
              onFilterChange({
                ...filters,
                severity: (e.target.value as Severity) || undefined,
              })
            }
            className="px-3 py-2 border border-gray-300 rounded-lg text-gray-700 bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* Start Date Filter */}
        <div className="flex flex-col">
          <label htmlFor="start-date-filter" className="text-sm font-medium text-gray-700 mb-1">
            Start Date
          </label>
          <input
            id="start-date-filter"
            type="date"
            value={formatDateForInput(filters.start_date)}
            onChange={(e) =>
              onFilterChange({
                ...filters,
                start_date: e.target.value || undefined,
              })
            }
            className="px-3 py-2 border border-gray-300 rounded-lg text-gray-700 bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* End Date Filter */}
        <div className="flex flex-col">
          <label htmlFor="end-date-filter" className="text-sm font-medium text-gray-700 mb-1">
            End Date
          </label>
          <input
            id="end-date-filter"
            type="date"
            value={formatDateForInput(filters.end_date)}
            onChange={(e) =>
              onFilterChange({
                ...filters,
                end_date: e.target.value || undefined,
              })
            }
            className="px-3 py-2 border border-gray-300 rounded-lg text-gray-700 bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Clear Filters Button */}
        {hasActiveFilters && (
          <button
            onClick={onClearFilters}
            className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Clear Filters
          </button>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Violation Summary Component
// ============================================================================

interface ViolationSummaryProps {
  violations: ViolationResponse[];
}

function ViolationSummary({ violations }: ViolationSummaryProps) {
  const summary = {
    total: violations.length,
    critical: violations.filter((v) => v.severity === 'critical').length,
    high: violations.filter((v) => v.severity === 'high').length,
    medium: violations.filter((v) => v.severity === 'medium').length,
    low: violations.filter((v) => v.severity === 'low').length,
  };

  return (
    <div className="flex flex-wrap gap-4 mb-4">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg">
        <span className="text-sm text-gray-600">Total:</span>
        <span className="text-sm font-semibold text-gray-900">{summary.total}</span>
      </div>
      {summary.critical > 0 && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-red-100 rounded-lg">
          <span className="w-2 h-2 rounded-full bg-red-500" />
          <span className="text-sm font-medium text-red-800">{summary.critical} Critical</span>
        </div>
      )}
      {summary.high > 0 && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-orange-100 rounded-lg">
          <span className="w-2 h-2 rounded-full bg-orange-500" />
          <span className="text-sm font-medium text-orange-800">{summary.high} High</span>
        </div>
      )}
      {summary.medium > 0 && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-yellow-100 rounded-lg">
          <span className="w-2 h-2 rounded-full bg-yellow-500" />
          <span className="text-sm font-medium text-yellow-800">{summary.medium} Medium</span>
        </div>
      )}
      {summary.low > 0 && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-green-100 rounded-lg">
          <span className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-sm font-medium text-green-800">{summary.low} Low</span>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main ViolationList Component
// ============================================================================

/**
 * ViolationList Component
 *
 * Displays a filterable table of compliance violations with:
 * - Filter controls for status, severity, and date range
 * - Severity indicators with color coding
 * - Status badges
 * - Click to select/view details
 * - Loading and empty states
 */
export function ViolationList({
  onSelectViolation,
  selectedViolationId,
  initialFilters = {},
}: ViolationListProps) {
  const [violations, setViolations] = useState<ViolationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<ViolationFilters>(initialFilters);

  const fetchViolations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response: PaginatedResponse<ViolationResponse> = await getViolations(filters);
      setViolations(response.items);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load violations';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchViolations();
  }, [fetchViolations]);

  const handleFilterChange = useCallback((newFilters: ViolationFilters) => {
    setFilters(newFilters);
  }, []);

  const handleClearFilters = useCallback(() => {
    setFilters({});
  }, []);

  const handleRowClick = useCallback(
    (violation: ViolationResponse) => {
      onSelectViolation?.(violation);
    },
    [onSelectViolation]
  );

  const hasActiveFilters = Boolean(
    filters.status || filters.severity || filters.rule_id || filters.start_date || filters.end_date
  );

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      <FilterBar
        filters={filters}
        onFilterChange={handleFilterChange}
        onClearFilters={handleClearFilters}
      />

      {/* Violation Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {/* Error State */}
        {error && <ErrorDisplay message={error} onRetry={fetchViolations} />}

        {/* Loading State */}
        {loading && !error && <LoadingSkeleton />}

        {/* Empty State */}
        {!loading && !error && violations.length === 0 && (
          <EmptyState hasFilters={hasActiveFilters} />
        )}

        {/* Violations Table */}
        {!loading && !error && violations.length > 0 && (
          <>
            {/* Summary */}
            <div className="p-4 border-b border-gray-200">
              <ViolationSummary violations={violations} />
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th
                      scope="col"
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      Severity
                    </th>
                    <th
                      scope="col"
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      Rule Code
                    </th>
                    <th
                      scope="col"
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      Record ID
                    </th>
                    <th
                      scope="col"
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      Status
                    </th>
                    <th
                      scope="col"
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      Detected
                    </th>
                    <th
                      scope="col"
                      className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {violations.map((violation) => (
                    <tr
                      key={violation.id}
                      onClick={() => handleRowClick(violation)}
                      className={`cursor-pointer transition-colors ${
                        selectedViolationId === violation.id
                          ? 'bg-blue-50'
                          : 'hover:bg-gray-50'
                      }`}
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <SeverityIndicator severity={violation.severity} />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="text-sm font-medium text-blue-600">
                          {violation.rule_code}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="text-sm text-gray-900 font-mono">
                          {violation.record_identifier}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <StatusBadge status={violation.status} />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="text-sm text-gray-500">
                          {formatDate(violation.detected_at)}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRowClick(violation);
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg transition-colors"
                          title="View details"
                        >
                          <ViewIcon />
                          <span>View</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default ViolationList;
