/**
 * Violations API functions for managing compliance violations.
 */

import apiClient, { buildQueryParams, handleApiResponse } from './client';
import type {
  PaginatedResponse,
  ReviewDecision,
  Violation,
  ViolationFilters,
  ViolationResponse,
} from './types';
import { ReviewActionType } from './types';

/**
 * Get violations with optional filtering.
 * @param filters - Optional filter parameters
 * @returns Paginated list of violations
 */
export async function getViolations(
  filters?: ViolationFilters
): Promise<PaginatedResponse<ViolationResponse>> {
  const queryString = filters ? buildQueryParams(filters as Record<string, unknown>) : '';
  return handleApiResponse(
    apiClient.get<PaginatedResponse<ViolationResponse>>(`/violations${queryString}`)
  );
}

/**
 * Get all violations without pagination (for smaller datasets).
 * @param filters - Optional filter parameters
 * @returns List of all matching violations
 */
export async function getAllViolations(
  filters?: Omit<ViolationFilters, 'skip' | 'limit'>
): Promise<ViolationResponse[]> {
  const queryString = filters ? buildQueryParams(filters as Record<string, unknown>) : '';
  return handleApiResponse(
    apiClient.get<ViolationResponse[]>(`/violations${queryString}`)
  );
}

/**
 * Get a specific violation by ID.
 * @param id - The violation ID
 * @returns The violation details
 */
export async function getViolation(id: string): Promise<Violation> {
  return handleApiResponse(
    apiClient.get<Violation>(`/violations/${id}`)
  );
}

/**
 * Submit a review decision for a violation.
 * @param id - The violation ID
 * @param decision - The review decision
 * @returns The updated violation
 */
export async function reviewViolation(
  id: string,
  decision: ReviewDecision
): Promise<Violation> {
  return handleApiResponse(
    apiClient.patch<Violation>(`/violations/${id}/review`, decision)
  );
}

/**
 * Confirm a violation.
 * @param id - The violation ID
 * @param notes - Optional notes
 * @param reviewerId - Optional reviewer ID
 * @returns The updated violation
 */
export async function confirmViolation(
  id: string,
  notes?: string,
  reviewerId?: string
): Promise<Violation> {
  return reviewViolation(id, {
    action: ReviewActionType.CONFIRM,
    notes,
    reviewer_id: reviewerId,
  });
}

/**
 * Mark a violation as false positive.
 * @param id - The violation ID
 * @param notes - Optional notes explaining why it's a false positive
 * @param reviewerId - Optional reviewer ID
 * @returns The updated violation
 */
export async function markFalsePositive(
  id: string,
  notes?: string,
  reviewerId?: string
): Promise<Violation> {
  return reviewViolation(id, {
    action: ReviewActionType.FALSE_POSITIVE,
    notes,
    reviewer_id: reviewerId,
  });
}

/**
 * Resolve a violation.
 * @param id - The violation ID
 * @param notes - Optional notes about the resolution
 * @param reviewerId - Optional reviewer ID
 * @returns The updated violation
 */
export async function resolveViolation(
  id: string,
  notes?: string,
  reviewerId?: string
): Promise<Violation> {
  return reviewViolation(id, {
    action: ReviewActionType.RESOLVE,
    notes,
    reviewer_id: reviewerId,
  });
}

export const violationsApi = {
  getAll: getViolations,
  getAllUnpaginated: getAllViolations,
  getById: getViolation,
  review: reviewViolation,
  confirm: confirmViolation,
  markFalsePositive,
  resolve: resolveViolation,
};
