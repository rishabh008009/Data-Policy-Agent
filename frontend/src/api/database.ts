/**
 * Database API functions for managing database connections and scans.
 */

import apiClient, { handleApiResponse } from './client';
import type {
  ConnectionTestResult,
  DatabaseConnection,
  DatabaseSchema,
  DBConnectionConfig,
  ScanRequest,
  ScanResult,
} from './types';

/**
 * Test and save a database connection.
 * @param config - The database connection configuration
 * @returns The connection test result
 */
export async function connectDatabase(config: DBConnectionConfig): Promise<ConnectionTestResult> {
  return handleApiResponse(
    apiClient.post<ConnectionTestResult>('/database/connect', config)
  );
}

/**
 * Get the active database connection.
 * @returns The active database connection or null
 */
export async function getActiveConnection(): Promise<DatabaseConnection | null> {
  try {
    return await handleApiResponse(
      apiClient.get<DatabaseConnection>('/database/connection')
    );
  } catch {
    return null;
  }
}

/**
 * Get the target database schema.
 * @returns The database schema with tables and columns
 */
export async function getDatabaseSchema(): Promise<DatabaseSchema> {
  return handleApiResponse(
    apiClient.get<DatabaseSchema>('/database/schema')
  );
}

/**
 * Trigger a manual compliance scan.
 * @param request - Optional scan configuration (specific rule IDs)
 * @returns The scan result
 */
export async function triggerScan(request?: ScanRequest): Promise<ScanResult> {
  return handleApiResponse(
    apiClient.post<ScanResult>('/database/scan', request || {}, {
      timeout: 300000, // 5 minute timeout for scans
    })
  );
}

export const databaseApi = {
  connect: connectDatabase,
  getActiveConnection,
  getSchema: getDatabaseSchema,
  scan: triggerScan,
};
