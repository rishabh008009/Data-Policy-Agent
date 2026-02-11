/**
 * ReviewPanel Component - Human review decision interface
 * Requirements: 4.3, 4.4, 4.6
 */

import { useCallback, useState } from 'react';
import { confirmViolation, markFalsePositive, resolveViolation } from '../api/violations';
import type { Violation, ViolationStatus } from '../api/types';

interface ReviewPanelProps {
  violationId: string;
  currentStatus: ViolationStatus;
  onReviewComplete?: (updatedViolation: Violation) => void;
  onError?: (error: string) => void;
}

type ReviewAction = 'confirm' | 'false_positive' | 'resolve';

export function ReviewPanel({ violationId, currentStatus, onReviewComplete, onError }: ReviewPanelProps) {
  const [notes, setNotes] = useState('');
  const [loadingAction, setLoadingAction] = useState<ReviewAction | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleAction = useCallback(async (action: ReviewAction) => {
    setLoadingAction(action);
    setSuccessMessage(null);
    try {
      const reviewNotes = notes.trim() || undefined;
      let result: Violation;
      if (action === 'confirm') result = await confirmViolation(violationId, reviewNotes);
      else if (action === 'false_positive') result = await markFalsePositive(violationId, reviewNotes);
      else result = await resolveViolation(violationId, reviewNotes);
      setSuccessMessage(action === 'confirm' ? 'Confirmed' : action === 'false_positive' ? 'Marked as false positive' : 'Resolved');
      setNotes('');
      onReviewComplete?.(result);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Failed to submit review');
    } finally {
      setLoadingAction(null);
    }
  }, [violationId, notes, onReviewComplete, onError]);

  const isLoading = loadingAction !== null;
  const canReview = currentStatus === 'pending' || currentStatus === 'confirmed';

  const statusMessages: Record<ViolationStatus, string> = {
    pending: 'This violation is pending review',
    confirmed: 'This violation has been confirmed',
    false_positive: 'Marked as false positive',
    resolved: 'This violation has been resolved',
  };

  const statusColors: Record<ViolationStatus, string> = {
    pending: 'bg-yellow-50 border-yellow-200 text-yellow-700',
    confirmed: 'bg-red-50 border-red-200 text-red-700',
    false_positive: 'bg-gray-50 border-gray-200 text-gray-700',
    resolved: 'bg-green-50 border-green-200 text-green-700',
  };

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">Review Decision</h3>
      </div>
      <div className="p-6 space-y-4">
        <div className={`p-3 rounded-lg border ${statusColors[currentStatus]}`}>
          <p className="text-sm font-medium">{statusMessages[currentStatus]}</p>
        </div>
        {successMessage && <div className="p-3 rounded-lg border border-green-200 bg-green-50 text-green-700 text-sm">{successMessage}</div>}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Notes (Optional)</label>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Add review notes..." rows={3} disabled={isLoading} className="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50" />
        </div>
        {canReview && (
          <div className="grid grid-cols-3 gap-3">
            <button onClick={() => handleAction('confirm')} disabled={isLoading || currentStatus === 'confirmed'} className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed">
              {loadingAction === 'confirm' ? 'Loading...' : 'Confirm'}
            </button>
            <button onClick={() => handleAction('false_positive')} disabled={isLoading} className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed">
              {loadingAction === 'false_positive' ? 'Loading...' : 'False Positive'}
            </button>
            <button onClick={() => handleAction('resolve')} disabled={isLoading} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed">
              {loadingAction === 'resolve' ? 'Loading...' : 'Resolve'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default ReviewPanel;
