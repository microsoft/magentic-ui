import { useEffect, useState } from "react";
import { TaskStateManager, StorageError } from "../utils/TaskStateManager";

interface ToastProps {
  error: StorageError;
  onDismiss: () => void;
}

const Toast = ({ error, onDismiss }: ToastProps) => {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 8000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  const getIcon = () => {
    switch (error.type) {
      case "quota_exceeded":
        return "💾";
      case "unavailable":
        return "⚠️";
      case "corrupted":
        return "🔧";
      default:
        return "❌";
    }
  };

  const getTitle = () => {
    switch (error.type) {
      case "quota_exceeded":
        return "Storage Full";
      case "unavailable":
        return "Storage Unavailable";
      case "corrupted":
        return "Data Issue";
      default:
        return "Storage Error";
    }
  };

  return (
    <div className="fixed bottom-4 right-4 max-w-sm bg-white border-l-4 border-orange-500 rounded-lg shadow-lg p-4 animate-slide-up z-50">
      <div className="flex items-start space-x-3">
        <div className="text-2xl">{getIcon()}</div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-gray-900">{getTitle()}</h4>
          <p className="text-sm text-gray-700 mt-1">{error.message}</p>
          <p className="text-xs text-gray-500 mt-1">Task: {error.taskId}</p>
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

export const StorageErrorToast = () => {
  const [errors, setErrors] = useState<(StorageError & { id: string })[]>([]);

  useEffect(() => {
    const unsubscribe = TaskStateManager.onError((error) => {
      const errorWithId = { ...error, id: Date.now().toString() };
      setErrors((prev) => [...prev, errorWithId]);
    });

    return unsubscribe;
  }, []);

  const dismissError = (id: string) => {
    setErrors((prev) => prev.filter((error) => error.id !== id));
  };

  return (
    <>
      {errors.map((error) => (
        <Toast
          key={error.id}
          error={error}
          onDismiss={() => dismissError(error.id)}
        />
      ))}
    </>
  );
};
