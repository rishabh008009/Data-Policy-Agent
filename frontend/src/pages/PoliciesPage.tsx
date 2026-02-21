/**
 * Policies page component - displays policy list and upload functionality.
 * 
 * Features:
 * - Policy list with filename, upload date, rule count, status
 * - Expandable policy detail view with extracted rules
 * - Toggle to enable/disable individual rules
 * - Integration with PolicyUploadForm component
 * - Loading and error states
 * 
 * Requirements: 1.3, 1.6
 */

import { useCallback, useEffect, useState } from 'react';
import { PolicyUploadForm } from '../components/PolicyUploadForm';
import {
  getPolicies,
  getPolicy,
  deletePolicy,
  updateRule,
} from '../api';
import type {
  PolicyResponse,
  PolicyUploadResponse,
  PolicyWithRules,
  ComplianceRule,
  ApiError,
  PolicyStatus,
} from '../api/types';

/**
 * Format date for display
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Get status badge color classes
 */
function getStatusBadgeClasses(status: PolicyStatus | string): string {
  switch (status) {
    case 'completed':
      return 'bg-green-100 text-green-800';
    case 'processing':
      return 'bg-blue-100 text-blue-800';
    case 'pending':
      return 'bg-yellow-100 text-yellow-800';
    case 'failed':
      return 'bg-red-100 text-red-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

/**
 * Get severity badge color classes
 */
function getSeverityBadgeClasses(severity: string): string {
  switch (severity) {
    case 'critical':
      return 'bg-red-100 text-red-800';
    case 'high':
      return 'bg-orange-100 text-orange-800';
    case 'medium':
      return 'bg-yellow-100 text-yellow-800';
    case 'low':
      return 'bg-green-100 text-green-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

/**
 * Document icon SVG component
 */
const DocumentIcon = () => (
  <svg
    className="w-5 h-5 text-gray-400"
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
    />
  </svg>
);

/**
 * Chevron icon for expandable sections
 */
const ChevronIcon = ({ expanded }: { expanded: boolean }) => (
  <svg
    className={`w-5 h-5 text-gray-400 transition-transform duration-200 ${
      expanded ? 'rotate-180' : ''
    }`}
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M19 9l-7 7-7-7"
    />
  </svg>
);

/**
 * Trash icon for delete button
 */
const TrashIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
    />
  </svg>
);

/**
 * Loading spinner component
 */
const LoadingSpinner = () => (
  <div className="flex justify-center items-center py-12">
    <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
  </div>
);

/**
 * Rule toggle switch component
 */
interface RuleToggleProps {
  rule: ComplianceRule;
  onToggle: (ruleId: string, isActive: boolean) => void;
  disabled?: boolean;
}

function RuleToggle({ rule, onToggle, disabled }: RuleToggleProps) {
  const [isUpdating, setIsUpdating] = useState(false);

  const handleToggle = async () => {
    if (disabled || isUpdating) return;
    setIsUpdating(true);
    try {
      await onToggle(rule.id, !rule.is_active);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <button
      onClick={handleToggle}
      disabled={disabled || isUpdating}
      className={`
        relative inline-flex h-6 w-11 items-center rounded-full transition-colors
        ${rule.is_active ? 'bg-blue-600' : 'bg-gray-300'}
        ${disabled || isUpdating ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
      `}
      title={rule.is_active ? 'Disable rule' : 'Enable rule'}
    >
      <span
        className={`
          inline-block h-4 w-4 transform rounded-full bg-white transition-transform
          ${rule.is_active ? 'translate-x-6' : 'translate-x-1'}
        `}
      />
      {isUpdating && (
        <span className="absolute inset-0 flex items-center justify-center">
          <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
        </span>
      )}
    </button>
  );
}

/**
 * Policy detail panel component - shows rules for a policy
 */
interface PolicyDetailPanelProps {
  policy: PolicyWithRules | null;
  loading: boolean;
  onRuleToggle: (ruleId: string, isActive: boolean) => Promise<void>;
}

function PolicyDetailPanel({ policy, loading, onRuleToggle }: PolicyDetailPanelProps) {
  if (loading) {
    return (
      <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
        <div className="flex items-center justify-center py-4">
          <div className="w-5 h-5 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin mr-2"></div>
          <span className="text-gray-500">Loading rules...</span>
        </div>
      </div>
    );
  }

  if (!policy || !policy.rules || policy.rules.length === 0) {
    return (
      <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
        <p className="text-gray-500 text-center py-4">No rules extracted from this policy.</p>
      </div>
    );
  }

  return (
    <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
      <h4 className="text-sm font-medium text-gray-700 mb-3">
        Extracted Rules ({policy.rules.length})
      </h4>
      <div className="space-y-3">
        {policy.rules.map((rule) => (
          <div
            key={rule.id}
            className={`
              p-4 bg-white rounded-lg border transition-opacity
              ${rule.is_active ? 'border-gray-200' : 'border-gray-200 opacity-60'}
            `}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-blue-600">{rule.rule_code}</span>
                  <span className={`px-2 py-0.5 text-xs rounded-full ${getSeverityBadgeClasses(rule.severity)}`}>
                    {rule.severity}
                  </span>
                  {!rule.is_active && (
                    <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">
                      Disabled
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-700 mb-2">{rule.description}</p>
                <p className="text-xs text-gray-500">
                  <span className="font-medium">Criteria:</span> {rule.evaluation_criteria}
                </p>
                {rule.target_table && (
                  <p className="text-xs text-gray-500 mt-1">
                    <span className="font-medium">Target Table:</span> {rule.target_table}
                  </p>
                )}
              </div>
              <div className="flex-shrink-0">
                <RuleToggle rule={rule} onToggle={onRuleToggle} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Policy list item component
 */
interface PolicyListItemProps {
  policy: PolicyResponse;
  expanded: boolean;
  policyDetails: PolicyWithRules | null;
  loadingDetails: boolean;
  onExpand: () => void;
  onDelete: () => void;
  onRuleToggle: (ruleId: string, isActive: boolean) => Promise<void>;
  deleting: boolean;
}

function PolicyListItem({
  policy,
  expanded,
  policyDetails,
  loadingDetails,
  onExpand,
  onDelete,
  onRuleToggle,
  deleting,
}: PolicyListItemProps) {
  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      {/* Policy header row */}
      <div
        className="px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={onExpand}
      >
        <div className="flex items-center gap-4 flex-1 min-w-0">
          <DocumentIcon />
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-gray-900 truncate">{policy.filename}</h3>
            <p className="text-sm text-gray-500">
              Uploaded {formatDate(policy.uploaded_at)}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Rule count */}
          <div className="text-center">
            <p className="text-lg font-semibold text-gray-900">{policy.rule_count}</p>
            <p className="text-xs text-gray-500">rules</p>
          </div>

          {/* Status badge */}
          <span
            className={`px-3 py-1 text-sm rounded-full ${getStatusBadgeClasses(policy.status)}`}
          >
            {policy.status}
          </span>

          {/* Delete button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            disabled={deleting}
            className={`
              p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors
              ${deleting ? 'opacity-50 cursor-not-allowed' : ''}
            `}
            title="Delete policy"
          >
            {deleting ? (
              <div className="w-5 h-5 border-2 border-red-200 border-t-red-500 rounded-full animate-spin"></div>
            ) : (
              <TrashIcon />
            )}
          </button>

          {/* Expand chevron */}
          <ChevronIcon expanded={expanded} />
        </div>
      </div>

      {/* Expandable detail panel */}
      {expanded && (
        <PolicyDetailPanel
          policy={policyDetails}
          loading={loadingDetails}
          onRuleToggle={onRuleToggle}
        />
      )}
    </div>
  );
}

/**
 * Main Policies Page Component
 */
export function PoliciesPage() {
  const [policies, setPolicies] = useState<PolicyResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [expandedPolicyId, setExpandedPolicyId] = useState<string | null>(null);
  const [policyDetails, setPolicyDetails] = useState<Record<string, PolicyWithRules>>({});
  const [loadingDetails, setLoadingDetails] = useState<Record<string, boolean>>({});
  const [deletingPolicies, setDeletingPolicies] = useState<Record<string, boolean>>({});

  /**
   * Fetch all policies
   */
  const fetchPolicies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPolicies();
      setPolicies(data);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.detail || 'Failed to load policies');
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Fetch policy details (with rules)
   */
  const fetchPolicyDetails = useCallback(async (policyId: string) => {
    if (policyDetails[policyId]) return; // Already loaded

    setLoadingDetails((prev) => ({ ...prev, [policyId]: true }));
    try {
      const data = await getPolicy(policyId);
      setPolicyDetails((prev) => ({ ...prev, [policyId]: data }));
    } catch (err) {
      console.error('Failed to load policy details:', err);
    } finally {
      setLoadingDetails((prev) => ({ ...prev, [policyId]: false }));
    }
  }, [policyDetails]);

  /**
   * Handle policy expansion
   */
  const handleExpand = useCallback(
    (policyId: string) => {
      if (expandedPolicyId === policyId) {
        setExpandedPolicyId(null);
      } else {
        setExpandedPolicyId(policyId);
        fetchPolicyDetails(policyId);
      }
    },
    [expandedPolicyId, fetchPolicyDetails]
  );

  /**
   * Handle policy deletion
   */
  const handleDelete = useCallback(async (policyId: string) => {
    if (!confirm('Are you sure you want to delete this policy? This will also delete all associated rules.')) {
      return;
    }

    setDeletingPolicies((prev) => ({ ...prev, [policyId]: true }));
    try {
      await deletePolicy(policyId);
      setPolicies((prev) => prev.filter((p) => p.id !== policyId));
      if (expandedPolicyId === policyId) {
        setExpandedPolicyId(null);
      }
      // Clean up cached details
      setPolicyDetails((prev) => {
        const updated = { ...prev };
        delete updated[policyId];
        return updated;
      });
    } catch (err) {
      const apiError = err as ApiError;
      alert(apiError.detail || 'Failed to delete policy');
    } finally {
      setDeletingPolicies((prev) => ({ ...prev, [policyId]: false }));
    }
  }, [expandedPolicyId]);

  /**
   * Handle rule toggle (enable/disable)
   */
  const handleRuleToggle = useCallback(async (ruleId: string, isActive: boolean) => {
    try {
      const updatedRule = await updateRule(ruleId, { is_active: isActive });
      
      // Update the rule in the cached policy details
      setPolicyDetails((prev) => {
        const updated = { ...prev };
        for (const policyId of Object.keys(updated)) {
          const policy = updated[policyId];
          if (policy.rules) {
            const ruleIndex = policy.rules.findIndex((r) => r.id === ruleId);
            if (ruleIndex !== -1) {
              updated[policyId] = {
                ...policy,
                rules: [
                  ...policy.rules.slice(0, ruleIndex),
                  updatedRule,
                  ...policy.rules.slice(ruleIndex + 1),
                ],
              };
              break;
            }
          }
        }
        return updated;
      });
    } catch (err) {
      const apiError = err as ApiError;
      alert(apiError.detail || 'Failed to update rule');
      throw err; // Re-throw to let the toggle component know it failed
    }
  }, []);

  /**
   * Handle successful upload
   */
  const handleUploadSuccess = useCallback((_policy: PolicyUploadResponse) => {
    // Re-fetch the full policy list from the server to get accurate rule counts
    fetchPolicies();
    // Hide the upload form
    setShowUploadForm(false);
  }, [fetchPolicies]);

  // Load policies on mount
  useEffect(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Policies</h1>
          <p className="text-gray-600 mt-1">
            Manage your compliance policy documents
          </p>
        </div>
        <button
          onClick={() => setShowUploadForm(!showUploadForm)}
          className={`
            px-4 py-2 rounded-lg transition-colors
            ${showUploadForm
              ? 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              : 'bg-blue-600 text-white hover:bg-blue-700'
            }
          `}
        >
          {showUploadForm ? 'Cancel' : 'Upload Policy'}
        </button>
      </div>

      {/* Upload Form */}
      {showUploadForm && (
        <PolicyUploadForm
          onUploadSuccess={handleUploadSuccess}
          onUploadError={(error) => console.error('Upload error:', error)}
        />
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <svg
              className="w-5 h-5 text-red-500"
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
            <span className="text-red-700">{error}</span>
            <button
              onClick={fetchPolicies}
              className="ml-auto px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200 transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && <LoadingSpinner />}

      {/* Policy List */}
      {!loading && !error && policies.length > 0 && (
        <div className="space-y-4">
          {policies.map((policy) => (
            <PolicyListItem
              key={policy.id}
              policy={policy}
              expanded={expandedPolicyId === policy.id}
              policyDetails={policyDetails[policy.id] || null}
              loadingDetails={loadingDetails[policy.id] || false}
              onExpand={() => handleExpand(policy.id)}
              onDelete={() => handleDelete(policy.id)}
              onRuleToggle={handleRuleToggle}
              deleting={deletingPolicies[policy.id] || false}
            />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && policies.length === 0 && !showUploadForm && (
        <div className="bg-white rounded-lg shadow p-6">
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
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              No Policies Yet
            </h3>
            <p className="mt-2 text-gray-500">
              Upload a PDF policy document to get started with compliance monitoring.
            </p>
            <button
              onClick={() => setShowUploadForm(true)}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Upload Your First Policy
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default PoliciesPage;
