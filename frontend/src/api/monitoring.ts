/**
 * Monitoring API functions for managing scheduled scans.
 */

import apiClient, { handleApiResponse } from './client';
import type { MonitoringConfig, ScheduleConfig, SchedulerStatus } from './types';

/**
 * Get the current scheduler status.
 * @returns The scheduler status including next run time
 */
export async function getMonitoringStatus(): Promise<SchedulerStatus> {
  return handleApiResponse(
    apiClient.get<SchedulerStatus>('/monitoring/status')
  );
}

/**
 * Configure the scan schedule.
 * @param config - The schedule configuration
 * @returns The updated monitoring configuration
 */
export async function configureSchedule(config: ScheduleConfig): Promise<MonitoringConfig> {
  return handleApiResponse(
    apiClient.post<MonitoringConfig>('/monitoring/schedule', config)
  );
}

/**
 * Disable scheduled scans.
 * @returns Success message
 */
export async function disableSchedule(): Promise<{ message: string }> {
  return handleApiResponse(
    apiClient.delete<{ message: string }>('/monitoring/schedule')
  );
}

/**
 * Enable scheduled scans with a specific interval.
 * @param intervalMinutes - The interval in minutes (60-1440)
 * @returns The updated monitoring configuration
 */
export async function enableSchedule(intervalMinutes: number): Promise<MonitoringConfig> {
  return configureSchedule({ interval_minutes: intervalMinutes });
}

export const monitoringApi = {
  getStatus: getMonitoringStatus,
  configure: configureSchedule,
  disable: disableSchedule,
  enable: enableSchedule,
};
