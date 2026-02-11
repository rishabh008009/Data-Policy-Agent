/**
 * ViolationsPage - Main page for viewing and managing compliance violations
 * Requirements: 4.2, 4.3, 4.4, 6.3, 6.5, 7.3
 */

import { useCallback, useState } from 'react';
import ViolationList from '../components/ViolationList';
import ViolationDetail from '../components/ViolationDetail';
import ReviewPanel from '../components/ReviewPanel';
import type { Violation, ViolationResponse } from '../api/types';

export function ViolationsPage() {
  const [selectedViolation, setSelectedViolation] = useState<ViolationResponse | null>(null);
  const [violationData, setViolationData] = useState<Violation | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSelectViolation = useCallback((violation: ViolationResponse) => {
    setSelectedViolation(violation);
    setViolationData(null);
    setErrorMessage(null);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedViolation(null);
    setViolationData(null);
    setErrorMessage(null);
  }, []);

  const handleViolationLoaded = useCallback((violation: Violation) => {
    setViolationData(violation);
  }, []);

  const handleReviewComplete = useCallback((updatedViolation: Violation) => {
    setViolationData(updatedViolation);
    setRefreshKey((prev) => prev + 1);
  }, []);

  const handleReviewError = useCallback((error: string) => {
    setErrorMessage(error);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Violations</h1>
        <p className="text-gray-600 mt-1">Review and manage compliance violations</p>
      </div>

      {errorMessage && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p className="text-red-800">{errorMessage}</p>
          <button onClick={() => setErrorMessage(null)} className="ml-auto p-1 text-red-600 hover:bg-red-100 rounded">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className={selectedViolation ? 'lg:col-span-2' : 'lg:col-span-3'}>
          <ViolationList
            key={refreshKey}
            onSelectViolation={handleSelectViolation}
            selectedViolationId={selectedViolation?.id}
          />
        </div>

        {selectedViolation && (
          <div className="lg:col-span-1 space-y-6">
            <ViolationDetail
              violationId={selectedViolation.id}
              ruleCode={selectedViolation.rule_code}
              ruleDescription={selectedViolation.rule_description}
              onClose={handleCloseDetail}
              onViolationLoaded={handleViolationLoaded}
            />
            {violationData && (
              <ReviewPanel
                violationId={selectedViolation.id}
                currentStatus={violationData.status}
                onReviewComplete={handleReviewComplete}
                onError={handleReviewError}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ViolationsPage;
