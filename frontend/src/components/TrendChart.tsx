/**
 * TrendChart component - displays violation trends over time using Recharts.
 * Requirements: 6.4, 8.4
 */

import { useEffect, useState, useCallback } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { getViolationTrends } from '../api';
import type { TimeRange, TrendBucket } from '../api';
import type { TrendData, TrendIndicator } from '../api/types';

/**
 * Time range options for the selector
 */
const TIME_RANGE_OPTIONS: { value: TimeRange; label: string }[] = [
  { value: '7d', label: '7 Days' },
  { value: '14d', label: '14 Days' },
  { value: '30d', label: '30 Days' },
  { value: '90d', label: '90 Days' },
];

/**
 * Format date string for display on chart
 */
function formatDateLabel(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateString;
  }
}

/**
 * Get trend indicator styling
 */
function getTrendIndicatorStyles(indicator: TrendIndicator): {
  bgColor: string;
  textColor: string;
  icon: React.ReactNode;
  label: string;
} {
  switch (indicator) {
    case 'improvement':
      return {
        bgColor: 'bg-green-100',
        textColor: 'text-green-800',
        icon: (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        ),
        label: 'Improving',
      };
    case 'degradation':
      return {
        bgColor: 'bg-red-100',
        textColor: 'text-red-800',
        icon: (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
          </svg>
        ),
        label: 'Degrading',
      };
    case 'stable':
    default:
      return {
        bgColor: 'bg-gray-100',
        textColor: 'text-gray-800',
        icon: (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14" />
          </svg>
        ),
        label: 'Stable',
      };
  }
}

/**
 * Format percentage change for display
 */
function formatPercentageChange(change: number | null): string {
  if (change === null) {
    return 'N/A';
  }
  const sign = change > 0 ? '+' : '';
  return `${sign}${change.toFixed(1)}%`;
}

/**
 * Loading skeleton for the chart
 */
function ChartLoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="flex justify-between items-center mb-4">
        <div className="h-6 bg-gray-200 rounded w-48"></div>
        <div className="h-10 bg-gray-200 rounded w-32"></div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-24 bg-gray-200 rounded"></div>
        ))}
      </div>
      <div className="h-64 bg-gray-200 rounded"></div>
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
        className="mx-auto h-10 w-10 text-red-400"
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
      <h3 className="mt-3 text-lg font-medium text-red-800">Failed to load trends</h3>
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
 * Summary card component
 */
interface SummaryCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  colorClass?: string;
}

function SummaryCard({ title, value, subtitle, colorClass = 'text-gray-900' }: SummaryCardProps) {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <p className="text-sm font-medium text-gray-600">{title}</p>
      <p className={`text-2xl font-bold ${colorClass}`}>{value}</p>
      {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
    </div>
  );
}

/**
 * Custom tooltip for the chart
 */
interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number;
    color: string;
  }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || !payload.length) {
    return null;
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3">
      <p className="font-medium text-gray-900 mb-2">{label}</p>
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center gap-2 text-sm">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-gray-600">{entry.name}:</span>
          <span className="font-medium">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * Props for TrendChart component
 */
export interface TrendChartProps {
  /** Initial time range to display */
  initialTimeRange?: TimeRange;
  /** Whether to show the time range selector */
  showTimeRangeSelector?: boolean;
  /** Whether to show the summary cards */
  showSummary?: boolean;
  /** Custom class name for the container */
  className?: string;
}

/**
 * TrendChart component - displays violation trends over time
 */
export function TrendChart({
  initialTimeRange = '7d',
  showTimeRangeSelector = true,
  showSummary = true,
  className = '',
}: TrendChartProps) {
  const [trendData, setTrendData] = useState<TrendData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>(initialTimeRange);

  const fetchTrendData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Use daily bucket for shorter ranges, weekly for longer
      const bucket: TrendBucket = timeRange === '90d' ? 'weekly' : 'daily';
      const data = await getViolationTrends(timeRange, bucket);
      setTrendData(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [timeRange]);

  useEffect(() => {
    fetchTrendData();
  }, [fetchTrendData]);

  // Handle time range change
  const handleTimeRangeChange = (newRange: TimeRange) => {
    setTimeRange(newRange);
  };

  // Loading state
  if (loading) {
    return (
      <div className={`bg-white rounded-lg shadow p-6 ${className}`}>
        <ChartLoadingSkeleton />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`bg-white rounded-lg shadow p-6 ${className}`}>
        <ErrorDisplay message={error} onRetry={fetchTrendData} />
      </div>
    );
  }

  // No data state
  if (!trendData || trendData.data_points.length === 0) {
    return (
      <div className={`bg-white rounded-lg shadow p-6 ${className}`}>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Violation Trends</h2>
          {showTimeRangeSelector && (
            <TimeRangeSelector value={timeRange} onChange={handleTimeRangeChange} />
          )}
        </div>
        <div className="text-center py-12 text-gray-500">
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
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
          <p className="mt-4">No trend data available for this period</p>
        </div>
      </div>
    );
  }

  // Prepare chart data with formatted labels
  const chartData = trendData.data_points.map((point) => ({
    ...point,
    dateLabel: formatDateLabel(point.date),
  }));

  // Get trend indicator styles
  const trendStyles = getTrendIndicatorStyles(trendData.summary.trend_indicator);

  return (
    <div className={`bg-white rounded-lg shadow p-6 ${className}`}>
      {/* Header with title and time range selector */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Violation Trends</h2>
        {showTimeRangeSelector && (
          <TimeRangeSelector value={timeRange} onChange={handleTimeRangeChange} />
        )}
      </div>

      {/* Summary Cards */}
      {showSummary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {/* Current Period Total */}
          <SummaryCard
            title="Current Period"
            value={trendData.summary.current_period_total}
            subtitle="Total violations"
          />

          {/* Previous Period Total */}
          <SummaryCard
            title="Previous Period"
            value={trendData.summary.previous_period_total}
            subtitle="Total violations"
          />

          {/* Percentage Change */}
          <SummaryCard
            title="Change"
            value={formatPercentageChange(trendData.summary.percentage_change)}
            subtitle="vs previous period"
            colorClass={
              trendData.summary.percentage_change === null
                ? 'text-gray-900'
                : trendData.summary.percentage_change > 0
                ? 'text-red-600'
                : trendData.summary.percentage_change < 0
                ? 'text-green-600'
                : 'text-gray-900'
            }
          />

          {/* Trend Indicator */}
          <div className={`rounded-lg p-4 ${trendStyles.bgColor}`}>
            <p className="text-sm font-medium text-gray-600">Trend</p>
            <div className={`flex items-center gap-2 mt-1 ${trendStyles.textColor}`}>
              {trendStyles.icon}
              <span className="text-xl font-bold">{trendStyles.label}</span>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {trendData.summary.total_new_violations} new, {trendData.summary.total_resolved_violations} resolved
            </p>
          </div>
        </div>
      )}

      {/* Chart */}
      <div className="h-64 sm:h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="dateLabel"
              tick={{ fontSize: 12, fill: '#6b7280' }}
              tickLine={{ stroke: '#e5e7eb' }}
              axisLine={{ stroke: '#e5e7eb' }}
            />
            <YAxis
              tick={{ fontSize: 12, fill: '#6b7280' }}
              tickLine={{ stroke: '#e5e7eb' }}
              axisLine={{ stroke: '#e5e7eb' }}
              allowDecimals={false}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ paddingTop: '20px' }}
              iconType="circle"
            />
            <Line
              type="monotone"
              dataKey="new_violations"
              name="New Violations"
              stroke="#ef4444"
              strokeWidth={2}
              dot={{ fill: '#ef4444', strokeWidth: 2, r: 4 }}
              activeDot={{ r: 6, strokeWidth: 2 }}
            />
            <Line
              type="monotone"
              dataKey="resolved_violations"
              name="Resolved"
              stroke="#22c55e"
              strokeWidth={2}
              dot={{ fill: '#22c55e', strokeWidth: 2, r: 4 }}
              activeDot={{ r: 6, strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/**
 * Time range selector component
 */
interface TimeRangeSelectorProps {
  value: TimeRange;
  onChange: (value: TimeRange) => void;
}

function TimeRangeSelector({ value, onChange }: TimeRangeSelectorProps) {
  return (
    <div className="flex rounded-lg border border-gray-200 overflow-hidden">
      {TIME_RANGE_OPTIONS.map((option) => (
        <button
          key={option.value}
          onClick={() => onChange(option.value)}
          className={`px-3 py-2 text-sm font-medium transition-colors ${
            value === option.value
              ? 'bg-blue-600 text-white'
              : 'bg-white text-gray-700 hover:bg-gray-50'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export default TrendChart;
