/**
 * Dashboard page component - displays compliance overview and summary statistics.
 * Requirements: 6.1, 6.2
 */

import { useEffect, useState } from 'react';
import { getDashboardSummary } from '../api';
import type { DashboardSummary, Severity } from '../api/types';
import { TrendChart } from '../components/TrendChart';

/**
 * Format a date string for display
 */
function formatDateTime(dateString: string | null): string {
  if (!dateString) {
    return 'Not available';
  }
  try {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return 'Invalid date';
  }
}

/**
 * Get severity color classes for styling
 */
function getSeverityColors(severity: Severity): { bg: string; text: string; border: string } {
  switch (severity) {
    case 'critical':
      return { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-200' };
    case 'high':
      return { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-200' };
    case 'medium':
      return { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-200' };
    case 'low':
      return { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-200' };
    default:
      return { bg: 'bg-gray-100', text: 'text-gray-800', border: 'border-gray-200' };
  }
}

/**
 * Summary card component for displaying a single metric
 */
interface SummaryCardProps {
  title: string;
  value: number;
  icon: React.ReactNode;
  colorClass: string;
  subtitle?: string;
}

function SummaryCard({ title, value, icon, colorClass, subtitle }: SummaryCardProps) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className={`text-3xl font-bold ${colorClass}`}>{value}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
        </div>
        <div className={`p-3 rounded-full ${colorClass.replace('text-', 'bg-').replace('-600', '-100').replace('-700', '-100')}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

/**
 * Severity badge component
 */
interface SeverityBadgeProps {
  severity: Severity;
  count: number;
}

function SeverityBadge({ severity, count }: SeverityBadgeProps) {
  const colors = getSeverityColors(severity);
  return (
    <div className={`flex items-center justify-between p-3 rounded-lg border ${colors.bg} ${colors.border}`}>
      <span className={`font-medium capitalize ${colors.text}`}>{severity}</span>
      <span className={`text-xl font-bold ${colors.text}`}>{count}</span>
    </div>
  );
}

/**
 * Loading skeleton component
 */
function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header skeleton */}
      <div>
        <div className="h-8 bg-gray-200 rounded w-48 mb-2"></div>
        <div className="h-4 bg-gray-200 rounded w-96"></div>
      </div>

      {/* Summary cards skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white rounded-lg shadow p-6">
            <div className="h-4 bg-gray-200 rounded w-24 mb-3"></div>
            <div className="h-8 bg-gray-200 rounded w-16"></div>
          </div>
        ))}
      </div>

      {/* Severity section skeleton */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="h-6 bg-gray-200 rounded w-48 mb-4"></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 bg-gray-200 rounded"></div>
          ))}
        </div>
      </div>

      {/* Scan info skeleton */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="h-6 bg-gray-200 rounded w-48 mb-4"></div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="h-20 bg-gray-200 rounded"></div>
          <div className="h-20 bg-gray-200 rounded"></div>
        </div>
      </div>
    </div>
  );
}

/**
 * Error display component
 */
interface ErrorDisplayProps {
  message: string;
  onRetry: () => void;
}

function ErrorDisplay({ message, onRetry }: ErrorDisplayProps) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
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
      <h3 className="mt-4 text-lg font-medium text-red-800">Failed to load dashboard</h3>
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
 * Icons for summary cards
 */
const TotalIcon = () => (
  <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

const PendingIcon = () => (
  <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const ConfirmedIcon = () => (
  <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
  </svg>
);

const ResolvedIcon = () => (
  <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const ClockIcon = () => (
  <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const CalendarIcon = () => (
  <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
  </svg>
);

/**
 * Main Dashboard Page Component
 */
export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDashboardSummary();
      setSummary(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  // Loading state
  if (loading) {
    return <LoadingSkeleton />;
  }

  // Error state
  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600 mt-1">
            Overview of your organization's compliance status
          </p>
        </div>
        <ErrorDisplay message={error} onRetry={fetchDashboardData} />
      </div>
    );
  }

  // No data state
  if (!summary) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600 mt-1">
            Overview of your organization's compliance status
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <p className="text-gray-500">No data available</p>
        </div>
      </div>
    );
  }

  // Severity order for display
  const severityOrder: Severity[] = ['critical', 'high', 'medium', 'low'];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-1">
          Overview of your organization's compliance status
        </p>
      </div>

      {/* Summary Cards - Row 1: Data Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <SummaryCard
          title="Policies Uploaded"
          value={summary.total_policies}
          icon={<TotalIcon />}
          colorClass="text-blue-600"
        />
        <SummaryCard
          title="Rules Extracted"
          value={summary.total_rules}
          icon={<ResolvedIcon />}
          colorClass="text-green-600"
          subtitle="From all policies"
        />
        <SummaryCard
          title="Transactions"
          value={summary.total_transactions}
          icon={<ConfirmedIcon />}
          colorClass="text-purple-600"
          subtitle="In database"
        />
        <SummaryCard
          title="Total Violations"
          value={summary.total_violations}
          icon={<PendingIcon />}
          colorClass="text-red-600"
        />
      </div>

      {/* Summary Cards - Row 2: Violation Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <SummaryCard
          title="Pending Review"
          value={summary.pending_count}
          icon={<PendingIcon />}
          colorClass="text-yellow-600"
          subtitle="Needs attention"
        />
        <SummaryCard
          title="Confirmed"
          value={summary.confirmed_count}
          icon={<ConfirmedIcon />}
          colorClass="text-red-600"
        />
        <SummaryCard
          title="Resolved"
          value={summary.resolved_count}
          icon={<ResolvedIcon />}
          colorClass="text-green-600"
        />
      </div>

      {/* Severity Breakdown */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Violations by Severity
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {severityOrder.map((severity) => (
            <SeverityBadge
              key={severity}
              severity={severity}
              count={summary.by_severity[severity] || 0}
            />
          ))}
        </div>
      </div>

      {/* Violation Trends Chart */}
      <TrendChart />

      {/* Scan Information */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Scan Information
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Last Scan */}
          <div className="flex items-start gap-4 p-4 bg-gray-50 rounded-lg">
            <div className="p-2 bg-white rounded-lg shadow-sm">
              <ClockIcon />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-600">Last Scan</p>
              <p className="text-lg font-semibold text-gray-900">
                {formatDateTime(summary.last_scan_at)}
              </p>
              {summary.last_scan_at && (
                <p className="text-xs text-gray-500 mt-1">
                  Compliance check completed
                </p>
              )}
            </div>
          </div>

          {/* Next Scheduled Scan */}
          <div className="flex items-start gap-4 p-4 bg-gray-50 rounded-lg">
            <div className="p-2 bg-white rounded-lg shadow-sm">
              <CalendarIcon />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-600">Next Scheduled Scan</p>
              <p className="text-lg font-semibold text-gray-900">
                {formatDateTime(summary.next_scan_at)}
              </p>
              {!summary.next_scan_at && (
                <p className="text-xs text-gray-500 mt-1">
                  No scan scheduled - configure in Settings
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Quick Actions
        </h2>
        <div className="flex flex-wrap gap-4">
          <a
            href="/violations?status=pending"
            className="inline-flex items-center gap-2 px-4 py-2 bg-yellow-100 text-yellow-800 rounded-lg hover:bg-yellow-200 transition-colors"
          >
            <PendingIcon />
            <span>Review Pending ({summary.pending_count})</span>
          </a>
          <a
            href="/violations?severity=critical"
            className="inline-flex items-center gap-2 px-4 py-2 bg-red-100 text-red-800 rounded-lg hover:bg-red-200 transition-colors"
          >
            <ConfirmedIcon />
            <span>Critical Issues ({summary.by_severity.critical || 0})</span>
          </a>
          <a
            href="/policies"
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-100 text-blue-800 rounded-lg hover:bg-blue-200 transition-colors"
          >
            <TotalIcon />
            <span>Manage Policies</span>
          </a>
        </div>
      </div>
    </div>
  );
}

export default DashboardPage;
