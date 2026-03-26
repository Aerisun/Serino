import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useAuth } from "./useAuth";
import { ArrowRight, Github, Loader2, Lock, Mail, Sparkles, User } from "lucide-react";

async function getPublicOAuthAuthorizationUrl(provider: "google" | "github", returnTo: string) {
  const query = new URLSearchParams({ return_to: returnTo });
  const response = await fetch(`/api/v1/public/auth/oauth/${provider}/start?${query.toString()}`, {
    method: "GET",
    credentials: "include",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(String((payload as { detail?: string }).detail || "认证发起失败"));
  }
  return String((payload as { authorization_url?: string }).authorization_url || "");
}

function clearAdminAuthSearchParams() {
  const url = new URL(window.location.href);
  url.searchParams.delete("auth");
  url.searchParams.delete("admin_auth_provider");
  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
}

function providerLabel(provider: string) {
  return provider === "google" ? "Google" : provider === "github" ? "GitHub" : provider;
}

export default function LoginPage() {
  const { login, loginOptions, loginWithAdminEmail, exchangeSiteUserLogin } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [adminEmail, setAdminEmail] = useState("");
  const [adminError, setAdminError] = useState("");
  const [adminLoading, setAdminLoading] = useState(false);

  const oauthProviders = useMemo(
    () => (loginOptions?.oauth_providers ?? []).filter((provider): provider is "google" | "github" => (
      provider === "google" || provider === "github"
    )),
    [loginOptions?.oauth_providers],
  );

  useEffect(() => {
    const authResult = new URLSearchParams(window.location.search).get("auth");
    const provider = new URLSearchParams(window.location.search).get("admin_auth_provider");
    if (authResult !== "success" || !provider) {
      return;
    }
    clearAdminAuthSearchParams();
    setAdminLoading(true);
    setAdminError("");
    void exchangeSiteUserLogin()
      .catch((err) => {
        setAdminError(err instanceof Error ? err.message : "管理员登录失败");
      })
      .finally(() => setAdminLoading(false));
  }, [exchangeSiteUserLogin]);

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

  const handleAdminEmailLogin = async (e: FormEvent) => {
    e.preventDefault();
    setAdminError("");
    setAdminLoading(true);
    try {
      await loginWithAdminEmail(adminEmail);
    } catch (err) {
      setAdminError(err instanceof Error ? err.message : "管理员邮箱登录失败");
    } finally {
      setAdminLoading(false);
    }
  };

  const handleOAuthLogin = async (provider: "google" | "github") => {
    setAdminError("");
    setAdminLoading(true);
    try {
      const authorizationUrl = await getPublicOAuthAuthorizationUrl(provider, `/admin/login?admin_auth_provider=${provider}`);
      if (!authorizationUrl) {
        throw new Error("没有拿到可用的认证地址");
      }
      window.location.assign(authorizationUrl);
    } catch (err) {
      setAdminError(err instanceof Error ? err.message : "管理员认证发起失败");
      setAdminLoading(false);
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

        {loginOptions && (loginOptions.email_enabled || oauthProviders.length) ? (
          <div className="mt-6 space-y-4">
            <div className="login-divider" />
            <div className="space-y-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-white/46">
                  Bound Admin Identity
                </p>
                <p className="mt-2 text-sm leading-6 text-white/60">
                  使用在“访客 / 管理员认证”里已经绑定过的邮箱、Google 或 GitHub 身份直接进入后台。
                </p>
              </div>

              {oauthProviders.length ? (
                <div className="grid gap-3">
                  {oauthProviders.map((provider) => (
                    <button
                      key={provider}
                      type="button"
                      onClick={() => void handleOAuthLogin(provider)}
                      disabled={adminLoading}
                      className="group relative flex items-center justify-between overflow-hidden rounded-2xl border border-white/12 bg-white/6 px-4 py-3 text-left text-white transition hover:border-white/22 hover:bg-white/10 disabled:opacity-60"
                    >
                      <span className="absolute inset-0 opacity-0 transition group-hover:opacity-100" style={{ background: "linear-gradient(135deg, rgb(66 133 244 / 0.14), rgb(234 67 53 / 0.08), rgb(251 188 5 / 0.08), rgb(52 168 83 / 0.14))" }} />
                      <span className="relative flex items-center gap-3">
                        <span className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/12 bg-white/10">
                          {provider === "github" ? <Github size={16} /> : <Sparkles size={16} />}
                        </span>
                        <span>
                          <span className="block text-sm font-semibold">{providerLabel(provider)}</span>
                          <span className="block text-xs text-white/52">认证一次后自动换成后台管理员会话</span>
                        </span>
                      </span>
                      {adminLoading ? <Loader2 className="animate-spin" size={16} /> : <ArrowRight size={16} className="relative" />}
                    </button>
                  ))}
                </div>
              ) : null}

              {loginOptions.email_enabled ? (
                <form onSubmit={handleAdminEmailLogin} className="space-y-3 rounded-2xl border border-white/10 bg-white/6 p-4">
                  <div className="text-sm font-semibold text-white">管理员邮箱</div>
                  <div className="login-input-wrap rounded-xl border border-white/10 bg-white/4">
                    <Mail className="login-input-icon" size={18} strokeWidth={1.8} />
                    <input
                      type="email"
                      placeholder="Bound admin email"
                      value={adminEmail}
                      onChange={(event) => setAdminEmail(event.target.value)}
                      className="login-input"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={adminLoading || !adminEmail.trim()}
                    className="login-btn"
                  >
                    {adminLoading ? (
                      <>
                        <Loader2 className="login-btn-spinner" size={18} />
                        Signing in...
                      </>
                    ) : (
                      "Sign in with admin email"
                    )}
                  </button>
                </form>
              ) : null}

              {adminError ? <p className="login-error">{adminError}</p> : null}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
