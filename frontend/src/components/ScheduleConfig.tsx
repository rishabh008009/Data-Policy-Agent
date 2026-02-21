/**
 * ScheduleConfig Component - Monitoring schedule configuration
 * Requirements: 5.1, 5.6
 */

import { useCallback, useEffect, useState } from 'react';
import { configureSchedule, disableSchedule, getMonitoringStatus } from '../api/monitoring';
import { triggerScan } from '../api/database';
import type { SchedulerStatus } from '../api/types';

interface ScheduleConfigProps {
  onScheduleChange?: (status: SchedulerStatus) => void;
}

interface IntervalOption {
  value: number;
  label: string;
  description: string;
}

const intervalOptions: IntervalOption[] = [
  { value: 60, label: 'Hourly', description: 'Every hour' },
  { value: 120, label: 'Every 2 hours', description: 'Every 2 hours' },
  { value: 360, label: 'Every 6 hours', description: '4 times per day' },
  { value: 720, label: 'Every 12 hours', description: 'Twice per day' },
  { value: 1440, label: 'Daily', description: 'Once per day' },
];

function formatDateTime(dateString: string | null): string {
  if (!dateString) return 'N/A';
  try {
    const date = new Date(dateString);
    return date.toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch {
    return 'N/A';
  }
}

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return '';
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = date.getTime() - now.getTime();
    const diffMins = Math.round(diffMs / 60000);

    if (diffMins < 0) {
      const absMins = Math.abs(diffMins);
      if (absMins < 60) return `${absMins} minutes ago`;
      const hours = Math.floor(absMins / 60);
      if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
      const days = Math.floor(hours / 24);
      return `${days} day${days > 1 ? 's' : ''} ago`;
    } else {
      if (diffMins < 60) return `in ${diffMins} minutes`;
      const hours = Math.floor(diffMins / 60);
      if (hours < 24) return `in ${hours} hour${hours > 1 ? 's' : ''}`;
      const days = Math.floor(hours / 24);
      return `in ${days} day${days > 1 ? 's' : ''}`;
    }
  } catch {
    return '';
  }
}

export function ScheduleConfig({ onScheduleChange }: ScheduleConfigProps) {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [selectedInterval, setSelectedInterval] = useState<number>(60);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Load current status on mount
  useEffect(() => {
    async function loadStatus() {
      try {
        const currentStatus = await getMonitoringStatus();
        setStatus(currentStatus);
        if (currentStatus.interval_minutes) {
          setSelectedInterval(currentStatus.interval_minutes);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load monitoring status');
      } finally {
        setIsLoading(false);
      }
    }
    loadStatus();
  }, []);

  const handleIntervalChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedInterval(parseInt(e.target.value, 10));
    setError(null);
    setSuccessMessage(null);
  }, []);

  const handleRunScanNow = useCallback(async () => {
    setIsScanning(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const result = await triggerScan();
      setSuccessMessage(
        `Scan completed! Found ${result.total_violations} violation(s) across ${result.status === 'completed' ? 'all' : '0'} rules.`
      );
      // Refresh status to update last scan time
      const currentStatus = await getMonitoringStatus();
      setStatus(currentStatus);
    } catch (err: unknown) {
      const detail = (err && typeof err === 'object' && 'detail' in err)
        ? (err as { detail: string }).detail
        : 'Failed to run scan. Make sure the database is connected.';
      setError(detail);
    } finally {
      setIsScanning(false);
    }
  }, []);

  const handleEnableSchedule = useCallback(async () => {
    setIsSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const config = await configureSchedule({ interval_minutes: selectedInterval });
      const newStatus: SchedulerStatus = {
        is_enabled: config.is_enabled,
        interval_minutes: config.interval_minutes,
        next_run_at: config.next_run_at,
        last_run_at: config.last_run_at,
        is_running: false,
      };
      setStatus(newStatus);
      setSuccessMessage('Monitoring schedule enabled successfully!');
      onScheduleChange?.(newStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to enable schedule');
    } finally {
      setIsSaving(false);
    }
  }, [selectedInterval, onScheduleChange]);

  const handleDisableSchedule = useCallback(async () => {
    setIsSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      await disableSchedule();
      const newStatus: SchedulerStatus = {
        is_enabled: false,
        interval_minutes: status?.interval_minutes || 60,
        next_run_at: null,
        last_run_at: status?.last_run_at || null,
        is_running: false,
      };
      setStatus(newStatus);
      setSuccessMessage('Monitoring schedule disabled');
      onScheduleChange?.(newStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disable schedule');
    } finally {
      setIsSaving(false);
    }
  }, [status, onScheduleChange]);

  const handleUpdateSchedule = useCallback(async () => {
    if (!status?.is_enabled) {
      await handleEnableSchedule();
      return;
    }

    setIsSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const config = await configureSchedule({ interval_minutes: selectedInterval });
      const newStatus: SchedulerStatus = {
        is_enabled: config.is_enabled,
        interval_minutes: config.interval_minutes,
        next_run_at: config.next_run_at,
        last_run_at: config.last_run_at,
        is_running: status?.is_running || false,
      };
      setStatus(newStatus);
      setSuccessMessage('Schedule updated successfully!');
      onScheduleChange?.(newStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update schedule');
    } finally {
      setIsSaving(false);
    }
  }, [status, selectedInterval, handleEnableSchedule, onScheduleChange]);

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="h-10 bg-gray-200 rounded"></div>
          <div className="h-10 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  const isEnabled = status?.is_enabled || false;
  const hasIntervalChanged = status?.interval_minutes !== selectedInterval;

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Monitoring Schedule</h2>
        <p className="text-sm text-gray-500 mt-1">
          Configure automatic compliance scans at regular intervals
        </p>
      </div>

      <div className="p-6 space-y-6">
        {/* Status Indicator */}
        <div className={`p-4 rounded-lg border ${isEnabled ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${isEnabled ? 'bg-green-500' : 'bg-gray-400'}`} />
              <span className={`text-sm font-medium ${isEnabled ? 'text-green-700' : 'text-gray-600'}`}>
                {isEnabled ? 'Monitoring Active' : 'Monitoring Disabled'}
              </span>
            </div>
            {status?.is_running && (
              <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-700 text-xs font-medium rounded-full">
                <svg className="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Scan Running
              </span>
            )}
          </div>
        </div>

        {/* Run Scan Now Button */}
        <button
          onClick={handleRunScanNow}
          disabled={isScanning || isSaving}
          className="w-full px-4 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 font-medium"
        >
          {isScanning ? (
            <>
              <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Scanning... (this may take a few minutes)
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              Run Scan Now
            </>
          )}
        </button>

        {/* Error Message */}
        {error && (
          <div className="p-4 rounded-lg border border-red-200 bg-red-50">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm font-medium text-red-700">{error}</span>
            </div>
          </div>
        )}

        {/* Success Message */}
        {successMessage && (
          <div className="p-4 rounded-lg border border-green-200 bg-green-50">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-sm font-medium text-green-700">{successMessage}</span>
            </div>
          </div>
        )}

        {/* Scan Times */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Last Scan */}
          <div className="p-4 rounded-lg border border-gray-200 bg-gray-50">
            <div className="flex items-center gap-2 mb-2">
              <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm font-medium text-gray-700">Last Scan</span>
            </div>
            <p className="text-lg font-semibold text-gray-900">
              {formatDateTime(status?.last_run_at || null)}
            </p>
            {status?.last_run_at && (
              <p className="text-xs text-gray-500 mt-1">
                {formatRelativeTime(status.last_run_at)}
              </p>
            )}
          </div>

          {/* Next Scan */}
          <div className="p-4 rounded-lg border border-gray-200 bg-gray-50">
            <div className="flex items-center gap-2 mb-2">
              <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span className="text-sm font-medium text-gray-700">Next Scheduled Scan</span>
            </div>
            <p className="text-lg font-semibold text-gray-900">
              {isEnabled ? formatDateTime(status?.next_run_at || null) : 'Not scheduled'}
            </p>
            {isEnabled && status?.next_run_at && (
              <p className="text-xs text-gray-500 mt-1">
                {formatRelativeTime(status.next_run_at)}
              </p>
            )}
          </div>
        </div>

        {/* Interval Selector */}
        <div>
          <label htmlFor="interval" className="block text-sm font-medium text-gray-700 mb-2">
            Scan Interval
          </label>
          <select
            id="interval"
            value={selectedInterval}
            onChange={handleIntervalChange}
            disabled={isSaving}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
          >
            {intervalOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label} - {option.description}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500 mt-1">
            Select how often the system should automatically scan for compliance violations
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4 border-t border-gray-200">
          {isEnabled ? (
            <>
              <button
                onClick={handleUpdateSchedule}
                disabled={isSaving || !hasIntervalChanged}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isSaving ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Updating...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Update Schedule
                  </>
                )}
              </button>
              <button
                onClick={handleDisableSchedule}
                disabled={isSaving}
                className="px-4 py-2 border border-red-300 text-red-700 rounded-lg hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isSaving ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Disabling...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Disable Monitoring
                  </>
                )}
              </button>
            </>
          ) : (
            <button
              onClick={handleEnableSchedule}
              disabled={isSaving}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isSaving ? (
                <>
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Enabling...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Enable Monitoring
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ScheduleConfig;
