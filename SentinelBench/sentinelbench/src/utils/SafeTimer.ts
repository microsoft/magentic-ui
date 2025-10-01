type TimerCallback = () => void;
type ErrorHandler = (
  error: Error,
  timerType: "interval" | "timeout",
  id?: number,
) => void;

class SafeTimerManager {
  private static errorHandlers: Set<ErrorHandler> = new Set();

  static onError(handler: ErrorHandler): () => void {
    this.errorHandlers.add(handler);
    return () => this.errorHandlers.delete(handler);
  }

  private static handleError(
    error: Error,
    timerType: "interval" | "timeout",
    id?: number,
  ): void {
    console.error(`Timer error (${timerType}):`, error);

    this.errorHandlers.forEach((handler) => {
      try {
        handler(error, timerType, id);
      } catch (handlerError) {
        console.error("Error in timer error handler:", handlerError);
      }
    });
  }

  static safeSetInterval(callback: TimerCallback, delay: number): number {
    const safeCallback = () => {
      try {
        callback();
      } catch (error) {
        this.handleError(
          error instanceof Error ? error : new Error(String(error)),
          "interval",
        );
      }
    };

    return window.setInterval(safeCallback, delay);
  }

  static safeSetTimeout(callback: TimerCallback, delay: number): number {
    const safeCallback = () => {
      try {
        callback();
      } catch (error) {
        this.handleError(
          error instanceof Error ? error : new Error(String(error)),
          "timeout",
        );
      }
    };

    return window.setTimeout(safeCallback, delay);
  }

  static safeRequestAnimationFrame(callback: TimerCallback): number {
    const safeCallback = () => {
      try {
        callback();
      } catch (error) {
        this.handleError(
          error instanceof Error ? error : new Error(String(error)),
          "interval",
        );
      }
    };

    return requestAnimationFrame(safeCallback);
  }

  static clearInterval(id: number): void {
    try {
      clearInterval(id);
    } catch (error) {
      console.warn("Failed to clear interval:", error);
    }
  }

  static clearTimeout(id: number): void {
    try {
      clearTimeout(id);
    } catch (error) {
      console.warn("Failed to clear timeout:", error);
    }
  }

  static cancelAnimationFrame(id: number): void {
    try {
      cancelAnimationFrame(id);
    } catch (error) {
      console.warn("Failed to cancel animation frame:", error);
    }
  }
}

export const safeSetInterval =
  SafeTimerManager.safeSetInterval.bind(SafeTimerManager);
export const safeSetTimeout =
  SafeTimerManager.safeSetTimeout.bind(SafeTimerManager);
export const safeRequestAnimationFrame =
  SafeTimerManager.safeRequestAnimationFrame.bind(SafeTimerManager);
export const safeClearInterval =
  SafeTimerManager.clearInterval.bind(SafeTimerManager);
export const safeClearTimeout =
  SafeTimerManager.clearTimeout.bind(SafeTimerManager);
export const safeCancelAnimationFrame =
  SafeTimerManager.cancelAnimationFrame.bind(SafeTimerManager);
export const onTimerError = SafeTimerManager.onError.bind(SafeTimerManager);

export default SafeTimerManager;
