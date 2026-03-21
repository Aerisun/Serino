import { useState, type FormEvent } from "react";
import { useAuth } from "./useAuth";
import { User, Lock, Loader2 } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
    } catch {
      setError("Invalid username or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-bg">
      {/* Animated gradient blobs */}
      <div className="login-blob login-blob-1" />
      <div className="login-blob login-blob-2" />
      <div className="login-blob login-blob-3" />
      <div className="login-blob login-blob-4" />

      {/* Glass card */}
      <div className="login-card">
        {/* Shine overlay */}
        <div className="login-card-shine" />

        {/* Brand */}
        <div className="login-brand">
          <h1 className="login-brand-text">Aerisun</h1>
          <p className="login-brand-sub">Administration</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field-group">
            <div className="login-input-wrap">
              <User className="login-input-icon" size={18} strokeWidth={1.8} />
              <input
                id="username"
                type="text"
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                className="login-input"
              />
            </div>

            <div className="login-divider" />

            <div className="login-input-wrap">
              <Lock className="login-input-icon" size={18} strokeWidth={1.8} />
              <input
                id="password"
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="login-input"
              />
            </div>
          </div>

          {error && (
            <p className="login-error">{error}</p>
          )}

          <button type="submit" disabled={loading} className="login-btn">
            {loading ? (
              <>
                <Loader2 className="login-btn-spinner" size={18} />
                Signing in...
              </>
            ) : (
              "Sign in"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
