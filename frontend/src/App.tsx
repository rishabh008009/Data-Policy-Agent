import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import {
  DashboardPage,
  PoliciesPage,
  ViolationsPage,
  SettingsPage,
} from "./pages";
import Login from "./pages/Login";

/**
 * Main application component with routing configuration.
 * Uses React Router for navigation between pages.
 */
function App() {
  return (
    <Routes>
      {/* Public Route */}
      <Route path="/login" element={<Login />} />

      {/* Protected Layout Routes */}
      <Route path="/" element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="policies" element={<PoliciesPage />} />
        <Route path="violations" element={<ViolationsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}

export default App;
