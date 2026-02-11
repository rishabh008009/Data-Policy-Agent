/**
 * Settings page component - displays configuration options.
 * Requirements: 2.1, 5.1, 5.6
 */

import { DatabaseConfig } from '../components/DatabaseConfig';
import { ScheduleConfig } from '../components/ScheduleConfig';

export function SettingsPage() {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-1">
          Configure database connection and monitoring schedule
        </p>
      </div>

      {/* Database Connection Section */}
      <DatabaseConfig />

      {/* Monitoring Schedule Section */}
      <ScheduleConfig />
    </div>
  );
}

export default SettingsPage;
