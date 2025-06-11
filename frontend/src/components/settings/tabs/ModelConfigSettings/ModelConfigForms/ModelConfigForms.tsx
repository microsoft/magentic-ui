// Minimal requirements for a ModelCOnfig
export interface ModelConfig {
  provider: string;
  config: {
    model: string;
    [key: string]: any; // allows additional properties
  },
  [key: string]: any; // allows additional properties
}

// Common interface for all model config forms
export interface ModelConfigFormProps {
  onChange?: (config: ModelConfig) => void;
  onSubmit?: (config: ModelConfig) => void;
  value?: ModelConfig;
}
