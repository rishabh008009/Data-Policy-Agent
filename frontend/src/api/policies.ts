/**
 * Policy API functions for managing policy documents.
 */

import apiClient, { handleApiResponse } from './client';
import type { PolicyResponse, PolicyUploadResponse, PolicyWithRules } from './types';

/**
 * Upload a PDF policy document.
 * @param file - The PDF file to upload
 * @returns The upload response with rule count
 */
export async function uploadPolicy(file: File): Promise<PolicyUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  return handleApiResponse(
    apiClient.post<PolicyUploadResponse>('/policies/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 120000, // 2 minute timeout for PDF processing
    })
  );
}

/**
 * Get all policies.
 * @returns List of all policies with rule counts
 */
export async function getPolicies(): Promise<PolicyResponse[]> {
  return handleApiResponse(
    apiClient.get<PolicyResponse[]>('/policies')
  );
}

/**
 * Get a specific policy by ID with its rules.
 * @param id - The policy ID
 * @returns The policy with all associated rules
 */
export async function getPolicy(id: string): Promise<PolicyWithRules> {
  return handleApiResponse(
    apiClient.get<PolicyWithRules>(`/policies/${id}`)
  );
}

/**
 * Delete a policy and all its associated rules.
 * @param id - The policy ID to delete
 */
export async function deletePolicy(id: string): Promise<void> {
  await apiClient.delete(`/policies/${id}`);
}

export const policiesApi = {
  upload: uploadPolicy,
  getAll: getPolicies,
  getById: getPolicy,
  delete: deletePolicy,
};
