import React, { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

interface LoginResponse {
  token: string;
}

const Login: React.FC = () => {
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  const navigate = useNavigate();

  const handleLogin = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await axios.post<LoginResponse>(
        "/api/auth/login",
        {
          email,
          password,
        }
      );

      localStorage.setItem("token", response.data.token);
      navigate("/dashboard");
    } catch (err) {
      setError("Invalid email or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={containerStyle}>
      <h2>Login</h2>

      <form onSubmit={handleLogin} style={formStyle}>
        {error && <p style={errorStyle}>{error}</p>}

        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            setEmail(e.target.value)
          }
          required
          style={inputStyle}
        />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            setPassword(e.target.value)
          }
          required
          style={inputStyle}
        />

        <button type="submit" style={buttonStyle} disabled={loading}>
          {loading ? "Logging in..." : "Login"}
        </button>
      </form>
    </div>
  );
};

export default Login;

/* --- Simple Inline Styles (Optional) --- */

const containerStyle: React.CSSProperties = {
  maxWidth: "400px",
  margin: "100px auto",
  padding: "2rem",
  border: "1px solid #ddd",
  borderRadius: "8px",
  textAlign: "center",
};

const formStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
};

const inputStyle: React.CSSProperties = {
  padding: "0.8rem",
  borderRadius: "6px",
  border: "1px solid #ccc",
};

const buttonStyle: React.CSSProperties = {
  padding: "0.8rem",
  borderRadius: "6px",
  border: "none",
  backgroundColor: "#4f46e5",
  color: "white",
  cursor: "pointer",
};

const errorStyle: React.CSSProperties = {
  color: "red",
};
