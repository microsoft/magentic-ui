import { RouterProvider } from "react-router-dom";
import { router } from "./router";
import ErrorBoundary from "./components/ErrorBoundary";
import { StorageErrorToast } from "./components/StorageErrorToast";
import { URLValidationToast } from "./components/URLValidationToast";

export default function App() {
  return (
    <ErrorBoundary>
      <RouterProvider router={router} />
      <StorageErrorToast />
      <URLValidationToast />
    </ErrorBoundary>
  );
}
