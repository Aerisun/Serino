import axios from "axios";

const loginPath = new URL("login", window.location.origin + import.meta.env.BASE_URL).pathname;

const client = axios.create({
  baseURL: "/api/v1/admin",
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("admin_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("admin_token");
      window.location.assign(loginPath);
    }
    return Promise.reject(error);
  }
);

export default client;
