import { useCallback, useEffect, useState } from "react";
import { recordTaskCompletion, recordTaskView } from "./analytics";

export function useTaskAnalytics(taskId: string): {
  recordSuccess: () => Promise<void>;
} {
  const [startTime] = useState(Date.now());
  const [hasRecorded, setHasRecorded] = useState(false);

  useEffect(() => {
    recordTaskView(taskId, Date.now());
  }, [taskId]);

  const recordSuccess = useCallback(async () => {
    if (!hasRecorded) {
      await recordTaskCompletion(taskId, Date.now(), startTime);
      setHasRecorded(true);
    }
  }, [hasRecorded, taskId, startTime]);

  return { recordSuccess };
}
