interface ParameterConfig {
  name: string;
  defaultValue: number;
  validator?: (value: number) => boolean;
}

type ParsedParameters = {
  hasAnyParams: boolean;
  [key: string]: number | boolean;
};

interface ValidationError {
  parameter: string;
  providedValue: string;
  defaultUsed: number;
  reason: string;
}

type ValidationErrorCallback = (errors: ValidationError[]) => void;

export class URLParameterHandler {
  private static errorCallbacks: Set<ValidationErrorCallback> = new Set();

  static onValidationError(callback: ValidationErrorCallback): () => void {
    this.errorCallbacks.add(callback);
    return () => this.errorCallbacks.delete(callback);
  }

  /**
   * Public method to emit validation errors (for manual validation)
   */
  static emitValidationError(errors: ValidationError[]): void {
    this.emitValidationErrors(errors);
  }

  private static emitValidationErrors(errors: ValidationError[]): void {
    if (errors.length === 0) return;
    
    this.errorCallbacks.forEach(callback => {
      try {
        callback(errors);
      } catch (e) {
        console.error('Error in validation error callback:', e);
      }
    });
  }

  private static cleanURL() {
    try {
      const cleanUrl = window.location.pathname;
      window.history.replaceState({}, '', cleanUrl);
    } catch (error) {
      console.error('Error cleaning URL parameters:', error);
    }
  }

  static parseAndClean(configs: ParameterConfig[]): ParsedParameters {
    const urlParams = new URLSearchParams(window.location.search);
    const result: ParsedParameters = { hasAnyParams: false };
    const validationErrors: ValidationError[] = [];
    
    let hasValidParams = false;

    for (const config of configs) {
      const paramValue = urlParams.get(config.name);
      
      if (paramValue !== null) {
        hasValidParams = true;
        const parsedValue = parseInt(paramValue, 10);
        
        // Validate the parameter
        if (isNaN(parsedValue)) {
          validationErrors.push({
            parameter: config.name,
            providedValue: paramValue,
            defaultUsed: config.defaultValue,
            reason: 'Not a valid number'
          });
          result[config.name] = config.defaultValue;
        } else if (config.validator && !config.validator(parsedValue)) {
          validationErrors.push({
            parameter: config.name,
            providedValue: paramValue,
            defaultUsed: config.defaultValue,
            reason: 'Failed validation rules'
          });
          result[config.name] = config.defaultValue;
        } else {
          result[config.name] = parsedValue;
        }
      } else {
        result[config.name] = config.defaultValue;
      }
    }

    result.hasAnyParams = hasValidParams;

    // Emit validation errors with a slight delay to ensure toast components are mounted
    if (validationErrors.length > 0) {
      setTimeout(() => {
        this.emitValidationErrors(validationErrors);
      }, 100);
    }

    // Clean URL if any parameters were found
    if (hasValidParams) {
      this.cleanURL();
    }

    return result;
  }

  static shouldResetState(_taskId: string, savedState: Record<string, unknown> | null, newParams: ParsedParameters): boolean {
    if (!savedState) {
      return false; // No saved state, will initialize with defaults
    }

    // Only reset if we have URL parameters that differ from saved state
    if (!newParams.hasAnyParams) {
      return false; // No URL params, keep existing saved state
    }

    // URL parameters exist, check if any differ from saved state
    for (const [key, value] of Object.entries(newParams)) {
      if (key !== 'hasAnyParams' && savedState[key] !== undefined && savedState[key] !== value) {
        return true;
      }
    }

    return false;
  }

  // Helper to safely extract parameter values as numbers
  static getNumber<T extends ParsedParameters>(params: T, key: Exclude<keyof T, 'hasAnyParams'>): number {
    const value = params[key];
    return value as number;
  }
}