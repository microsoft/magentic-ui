import { useEffect, useState } from "react";
import { URLParameterHandler } from "../utils/urlParameterHandler";

interface ValidationError {
  parameter: string;
  providedValue: string;
  defaultUsed: number;
  reason: string;
}

interface ToastProps {
  errors: ValidationError[];
  onDismiss: () => void;
}

const ValidationToast = ({ errors, onDismiss }: ToastProps) => {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 10000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div className="fixed top-4 right-4 max-w-md bg-white border-l-4 border-yellow-500 rounded-lg shadow-lg p-4 animate-slide-down z-50">
      <div className="flex items-start space-x-3">
        <div className="text-2xl">⚠️</div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-gray-900">
            URL Parameter Issues
          </h4>
          <p className="text-sm text-gray-700 mt-1">
            Some URL parameters were invalid and have been corrected:
          </p>

          <div className="mt-2 space-y-1">
            {errors.map((error, index) => (
              <div
                key={index}
                className="text-xs bg-yellow-50 p-2 rounded border"
              >
                <div className="font-medium text-yellow-800">
                  Parameter:{" "}
                  <code className="bg-yellow-100 px-1 rounded">
                    {error.parameter}
                  </code>
                </div>
                <div className="text-yellow-700">
                  Provided:{" "}
                  <code className="bg-white px-1 rounded">
                    {error.providedValue}
                  </code>
                  → Using default:{" "}
                  <code className="bg-green-100 px-1 rounded">
                    {error.defaultUsed}
                  </code>
                </div>
                <div className="text-yellow-600 italic">{error.reason}</div>
              </div>
            ))}
          </div>

          <p className="text-xs text-gray-500 mt-2">
            The task will continue with default values. Check the URL format and
            try again.
          </p>
        </div>
        <button
          onClick={onDismiss}
          className="text-gray-400 hover:text-gray-600 transition-colors"
          aria-label="Dismiss notification"
        >
          ✕
        </button>
      </div>
    </div>
  );
};

interface ErrorGroup {
  id: string;
  errors: ValidationError[];
}

export const URLValidationToast = () => {
  const [errorGroups, setErrorGroups] = useState<ErrorGroup[]>([]);

  useEffect(() => {
    // Register listener immediately
    const unsubscribe = URLParameterHandler.onValidationError((errors) => {
      const errorGroup: ErrorGroup = {
        id: Date.now().toString(),
        errors: errors,
      };
      setErrorGroups((prev) => [...prev, errorGroup]);
    });

    // Also trigger validation check for current page immediately
    // This ensures we catch any validation errors from the current URL
    const currentUrl = new URL(window.location.href);
    if (currentUrl.searchParams.size > 0) {
      // Force a re-validation by triggering a custom event
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('revalidateParams'));
      }, 0);
    }

    return unsubscribe;
  }, []);

  const dismissErrors = (id: string) => {
    setErrorGroups((prev) => prev.filter((group) => group.id !== id));
  };

  return (
    <>
      {errorGroups.map((errorGroup) => (
        <ValidationToast
          key={errorGroup.id}
          errors={errorGroup.errors}
          onDismiss={() => dismissErrors(errorGroup.id)}
        />
      ))}
    </>
  );
};
