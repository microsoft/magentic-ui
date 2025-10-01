import { FormEvent, useEffect, useState } from "react";
import { Navigate, useLocation, useSearchParams } from "react-router-dom";

const SITE_PASSWORD = "microsoftaifrontiers";

export default function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [searchParams] = useSearchParams();
  const location = useLocation();

  // Get the intended path from the state, or default to "/"
  const from = location.state?.from?.pathname || "/";

  useEffect(() => {
    const urlPassword = searchParams.get("password");
    if (urlPassword === SITE_PASSWORD) {
      localStorage.setItem("isAuthenticated", "true");
      // Preserve the current pathname when redirecting
      const targetPath =
        location.pathname === "/login" ? from : location.pathname;
      window.location.href =
        targetPath + location.search.replace(`?password=${SITE_PASSWORD}`, "");
    }
  }, [searchParams, location, from]);

  // Check if already authenticated
  if (localStorage.getItem("isAuthenticated") === "true") {
    return <Navigate to={from} replace />;
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (password === SITE_PASSWORD) {
      localStorage.setItem("isAuthenticated", "true");
      window.location.href = from; // Redirect to the intended path
    } else {
      setError("Incorrect password");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div>
          <h2 className="text-center text-3xl font-bold text-gray-900">
            SentinelBench
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Enter the site password to continue
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="password" className="sr-only">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              className="appearance-none rounded relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
              placeholder="Enter password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <p className="text-red-500 text-sm text-center">{error}</p>}
          <div>
            <button
              type="submit"
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Sign in
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
