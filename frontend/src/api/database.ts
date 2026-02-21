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
  try {
    const data = await handleApiResponse(
      apiClient.post<DatabaseConnection & { message: string }>('/database/connect', config)
    );
    return {
      success: true,
      message: data.message || 'Connected successfully',
      connection: data,
    };
  } catch (err: unknown) {
    const detail = (err && typeof err === 'object' && 'detail' in err)
      ? (err as { detail: string }).detail
      : 'Connection failed';
    return {
      success: false,
      message: detail,
    };
  }
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
