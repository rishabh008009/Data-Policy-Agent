/**
 * ViolationDetail Component - Displays full violation details
 * Requirements: 4.2, 6.3, 7.3
 */

import { useCallback, useEffect, useState } from 'react';
import { getViolation } from '../api/violations';
import type { Severity, Violation, ViolationStatus } from '../api/types';

interface ViolationDetailProps {
  violationId: string;
  ruleCode?: string;
  ruleDescription?: string;
  onClose?: () => void;
  onViolationLoaded?: (violation: Violation) => void;
}

function getSeverityColors(severity: Severity) {
  const colors: Record<Severity, { bg: string; text: string; border: string }> = {
    critical: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
    high: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
    medium: { bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200' },
    low: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  };
  return colors[severity] || { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' };
}

function getStatusColors(status: ViolationStatus) {
  const colors: Record<ViolationStatus, { bg: string; text: string }> = {
    pending: { bg: 'bg-yellow-100', text: 'text-yellow-800' },
    confirmed: { bg: 'bg-red-100', text: 'text-red-800' },
    false_positive: { bg: 'bg-gray-100', text: 'text-gray-800' },
    resolved: { bg: 'bg-green-100', text: 'text-green-800' },
  };
  return colors[status] || { bg: 'bg-gray-100', text: 'text-gray-800' };
}

function formatStatus(status: ViolationStatus): string {
  const labels: Record<ViolationStatus, string> = {
    pending: 'Pending Review',
    confirmed: 'Confirmed',
    false_positive: 'False Positive',
    resolved: 'Resolved',
  };
  return labels[status] || status;
}

function formatDateTime(dateString: string): string {
  try {
    return new Date(dateString).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return 'Invalid date'; }
}

export function ViolationDetail({ violationId, ruleCode, ruleDescription, onClose, onViolationLoaded }: ViolationDetailProps) {
  const [violation, setViolation] = useState<Violation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchViolation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getViolation(violationId);
      setViolation(data);
      onViolationLoaded?.(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [violationId, onViolationLoaded]);

  useEffect(() => { fetchViolation(); }, [fetchViolation]);

  if (loading) return <div className="bg-white rounded-lg shadow p-6 animate-pulse"><div className="h-32 bg-gray-200 rounded" /></div>;
  if (error) return <div className="bg-white rounded-lg shadow p-6 text-center text-red-600">{error}</div>;
  if (!violation) return null;

  const sev = getSeverityColors(violation.severity);
  const stat = getStatusColors(violation.status);

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-semibold text-gray-900">{ruleCode || 'Details'}</h3>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${sev.bg} ${sev.text}`}>{violation.severity}</span>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${stat.bg} ${stat.text}`}>{formatStatus(violation.status)}</span>
          </div>
          {ruleDescription && <p className="mt-1 text-sm text-gray-600">{ruleDescription}</p>}
        </div>
        {onClose && <button onClick={onClose} className="p-2 text-gray-400 hover:text-gray-600 rounded-lg"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg></button>}
      </div>
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <div><p className="text-sm text-gray-500">Record ID</p><p className="font-mono bg-gray-50 px-3 py-2 rounded">{violation.record_identifier}</p></div>
          <div><p className="text-sm text-gray-500">Detected</p><p className="bg-gray-50 px-3 py-2 rounded">{formatDateTime(violation.detected_at)}</p></div>
        </div>
        <div><p className="text-sm text-gray-500 mb-2">Justification</p><div className={`p-4 rounded-lg border ${sev.border} ${sev.bg}`}><p className="whitespace-pre-wrap">{violation.justification || 'None'}</p></div></div>
        <div><p className="text-sm text-gray-500 mb-2">Remediation</p><div className="p-4 rounded-lg border border-blue-200 bg-blue-50"><p className="whitespace-pre-wrap">{violation.remediation_suggestion || 'Manual review required'}</p></div></div>
      </div>
    </div>
  );
}

export default ViolationDetail;
