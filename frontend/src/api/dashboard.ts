/**
 * Dashboard API functions for compliance overview and trends.
 */

import apiClient, { buildQueryParams, handleApiResponse } from './client';
import type { DashboardSummary, TrendData, TrendDataPoint } from './types';

/**
 * Get the compliance dashboard summary.
 * @returns The dashboard summary with violation counts
 */
export async function getDashboardSummary(): Promise<DashboardSummary> {
  return handleApiResponse(
    apiClient.get<DashboardSummary>('/dashboard/summary')
  );
}

/**
 * Time range options for trend data
 */
export type TimeRange = '7d' | '14d' | '30d' | '90d';

/**
 * Bucket granularity options for trend data
 */
export type TrendBucket = 'daily' | 'weekly';

/**
 * Get violation trends over time.
 * @param timeRange - Time range for trend data (default: '7d')
 * @param bucket - Time bucket granularity (default: 'daily')
 * @returns The trend data with data points and summary statistics
 */
export async function getViolationTrends(
  timeRange?: TimeRange,
  bucket?: TrendBucket
): Promise<TrendData> {
  const params: Record<string, unknown> = {};
  if (timeRange) params.time_range = timeRange;
  if (bucket) params.bucket = bucket;
  
  const queryString = buildQueryParams(params);
  return handleApiResponse(
    apiClient.get<TrendData>(`/dashboard/trends${queryString}`)
  );
}

/**
 * Get trend data points for charting.
 * @param timeRange - Time range for trend data (default: '7d')
 * @param bucket - Time bucket granularity (default: 'daily')
 * @returns Array of trend data points
 */
export async function getTrendDataPoints(
  timeRange?: TimeRange,
  bucket?: TrendBucket
): Promise<TrendDataPoint[]> {
  const trends = await getViolationTrends(timeRange, bucket);
  return trends.data_points;
}

export const dashboardApi = {
  getSummary: getDashboardSummary,
  getTrends: getViolationTrends,
  getTrendDataPoints,
};
