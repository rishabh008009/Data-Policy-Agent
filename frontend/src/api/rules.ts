/**
 * Rules API functions for managing compliance rules.
 */

import apiClient, { handleApiResponse } from './client';
import type { ComplianceRule, ComplianceRuleResponse, RuleUpdateRequest } from './types';

/**
 * Get all compliance rules.
 * @returns List of all compliance rules
 */
export async function getRules(): Promise<ComplianceRuleResponse[]> {
  return handleApiResponse(
    apiClient.get<ComplianceRuleResponse[]>('/rules')
  );
}

/**
 * Get a specific rule by ID.
 * @param id - The rule ID
 * @returns The rule details
 */
export async function getRule(id: string): Promise<ComplianceRule> {
  return handleApiResponse(
    apiClient.get<ComplianceRule>(`/rules/${id}`)
  );
}

/**
 * Update a rule (enable/disable).
 * @param id - The rule ID
 * @param update - The update data
 * @returns The updated rule
 */
export async function updateRule(id: string, update: RuleUpdateRequest): Promise<ComplianceRule> {
  return handleApiResponse(
    apiClient.patch<ComplianceRule>(`/rules/${id}`, update)
  );
}

/**
 * Enable a rule.
 * @param id - The rule ID
 * @returns The updated rule
 */
export async function enableRule(id: string): Promise<ComplianceRule> {
  return updateRule(id, { is_active: true });
}

/**
 * Disable a rule.
 * @param id - The rule ID
 * @returns The updated rule
 */
export async function disableRule(id: string): Promise<ComplianceRule> {
  return updateRule(id, { is_active: false });
}

export const rulesApi = {
  getAll: getRules,
  getById: getRule,
  update: updateRule,
  enable: enableRule,
  disable: disableRule,
};
