/**
 * DatabaseConfig Component - Database connection setup form
 * Requirements: 2.1, 5.1
 */

import { useCallback, useEffect, useState } from 'react';
import { connectDatabase, getActiveConnection } from '../api/database';
import type { DatabaseConnection, DBConnectionConfig } from '../api/types';

interface DatabaseConfigProps {
  onConnectionChange?: (connection: DatabaseConnection | null) => void;
}

interface FormData {
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
}

const initialFormData: FormData = {
  host: '',
  port: '5432',
  database: '',
  username: '',
  password: '',
};

export function DatabaseConfig({ onConnectionChange }: DatabaseConfigProps) {
  const [formData, setFormData] = useState<FormData>(initialFormData);
  const [activeConnection, setActiveConnection] = useState<DatabaseConnection | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isLoadingConnection, setIsLoadingConnection] = useState(true);

  // Load active connection on mount
  useEffect(() => {
    async function loadActiveConnection() {
      try {
        const connection = await getActiveConnection();
        setActiveConnection(connection);
        if (connection) {
          setFormData({
            host: connection.host,
            port: connection.port.toString(),
            database: connection.database_name,
            username: connection.username,
            password: '', // Don't populate password for security
          });
        }
      } catch {
        // No active connection, that's fine
      } finally {
        setIsLoadingConnection(false);
      }
    }
    loadActiveConnection();
  }, []);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError(null);
    setSuccessMessage(null);
  }, []);

  const validateForm = useCallback((): string | null => {
    if (!formData.host.trim()) return 'Host is required';
    if (!formData.database.trim()) return 'Database name is required';
    if (!formData.username.trim()) return 'Username is required';
    if (!formData.password.trim() && !activeConnection) return 'Password is required';
    const port = parseInt(formData.port, 10);
    if (isNaN(port) || port < 1 || port > 65535) return 'Port must be between 1 and 65535';
    return null;
  }, [formData, activeConnection]);

  const buildConfig = useCallback((): DBConnectionConfig => ({
    host: formData.host.trim(),
    port: parseInt(formData.port, 10) || 5432,
    database: formData.database.trim(),
    username: formData.username.trim(),
    password: formData.password,
  }), [formData]);

  const handleTestConnection = useCallback(async () => {
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsTesting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const result = await connectDatabase(buildConfig());
      if (result.success) {
        setSuccessMessage('Connection test successful!');
      } else {
        setError(result.message || 'Connection test failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to test connection');
    } finally {
      setIsTesting(false);
    }
  }, [validateForm, buildConfig]);

  const handleSaveConnection = useCallback(async () => {
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const result = await connectDatabase(buildConfig());
      if (result.success && result.connection) {
        setActiveConnection(result.connection);
        setSuccessMessage('Connection saved successfully!');
        setFormData((prev) => ({ ...prev, password: '' }));
        onConnectionChange?.(result.connection);
      } else {
        setError(result.message || 'Failed to save connection');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save connection');
    } finally {
      setIsLoading(false);
    }
  }, [validateForm, buildConfig, onConnectionChange]);

  const isProcessing = isLoading || isTesting;

  if (isLoadingConnection) {
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

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Database Connection</h2>
        <p className="text-sm text-gray-500 mt-1">
          Configure the PostgreSQL database to scan for compliance violations
        </p>
      </div>

      <div className="p-6 space-y-6">
        {/* Connection Status */}
        {activeConnection && (
          <div className="p-4 rounded-lg border border-green-200 bg-green-50">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm font-medium text-green-700">Connected</span>
            </div>
            <p className="text-sm text-green-600 mt-1">
              {activeConnection.username}@{activeConnection.host}:{activeConnection.port}/{activeConnection.database_name}
            </p>
          </div>
        )}

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

        {/* Form Fields */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Host */}
          <div>
            <label htmlFor="host" className="block text-sm font-medium text-gray-700 mb-1">
              Host <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="host"
              name="host"
              value={formData.host}
              onChange={handleInputChange}
              placeholder="localhost"
              disabled={isProcessing}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white text-black placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
            />
          </div>

          {/* Port */}
          <div>
            <label htmlFor="port" className="block text-sm font-medium text-gray-700 mb-1">
              Port
            </label>
            <input
              type="text"
              id="port"
              name="port"
              value={formData.port}
              onChange={handleInputChange}
              placeholder="5432"
              disabled={isProcessing}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white text-black placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
            />
          </div>

          {/* Database Name */}
          <div>
            <label htmlFor="database" className="block text-sm font-medium text-gray-700 mb-1">
              Database Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="database"
              name="database"
              value={formData.database}
              onChange={handleInputChange}
              placeholder="mydb"
              disabled={isProcessing}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white text-black placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
            />
          </div>

          {/* Username */}
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
              Username <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleInputChange}
              placeholder="postgres"
              disabled={isProcessing}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white text-black placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
            />
          </div>

          {/* Password */}
          <div className="md:col-span-2">
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Password {!activeConnection && <span className="text-red-500">*</span>}
            </label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleInputChange}
              placeholder={activeConnection ? '••••••••' : 'Enter password'}
              disabled={isProcessing}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white text-black placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
            />
            {activeConnection && (
              <p className="text-xs text-gray-500 mt-1">
                Leave blank to keep the existing password
              </p>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4 border-t border-gray-200">
          <button
            onClick={handleTestConnection}
            disabled={isProcessing}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isTesting ? (
              <>
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Testing...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Test Connection
              </>
            )}
          </button>

          <button
            onClick={handleSaveConnection}
            disabled={isProcessing}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isLoading ? (
              <>
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Saving...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                </svg>
                Save Connection
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default DatabaseConfig;
