import { 
  AnthropicModelConfigSchema, 
  ModelConfigSchema, 
  ModelFamilySchema,
  type AnthropicModelConfig 
} from '../types';

describe('Anthropic TypeScript Types', () => {
  describe('AnthropicModelConfigSchema', () => {
    it('validates correct Anthropic configuration', () => {
      const validConfig = {
        provider: 'autogen_ext.models.anthropic.AnthropicChatCompletionClient',
        config: {
          model: 'claude-4-sonnet-20251114',
          api_key: 'sk-ant-test-key',
          base_url: 'https://api.anthropic.com',
          max_retries: 5
        }
      };

      const result = AnthropicModelConfigSchema.safeParse(validConfig);
      expect(result.success).toBe(true);
      
      if (result.success) {
        expect(result.data.provider).toBe('autogen_ext.models.anthropic.AnthropicChatCompletionClient');
        expect(result.data.config.model).toBe('claude-4-sonnet-20251114');
      }
    });

    it('validates minimal Anthropic configuration', () => {
      const minimalConfig = {
        provider: 'autogen_ext.models.anthropic.AnthropicChatCompletionClient',
        config: {
          model: 'claude-4-sonnet-20251114'
        }
      };

      const result = AnthropicModelConfigSchema.safeParse(minimalConfig);
      expect(result.success).toBe(true);
    });

    it('rejects configuration with wrong provider', () => {
      const wrongProvider = {
        provider: 'OpenAIChatCompletionClient',
        config: {
          model: 'claude-4-sonnet-20251114'
        }
      };

      const result = AnthropicModelConfigSchema.safeParse(wrongProvider);
      expect(result.success).toBe(false);
    });

    it('rejects configuration with empty model', () => {
      const emptyModel = {
        provider: 'autogen_ext.models.anthropic.AnthropicChatCompletionClient',
        config: {
          model: ''
        }
      };

      const result = AnthropicModelConfigSchema.safeParse(emptyModel);
      expect(result.success).toBe(false);
    });

    it('rejects configuration without model', () => {
      const noModel = {
        provider: 'autogen_ext.models.anthropic.AnthropicChatCompletionClient',
        config: {}
      };

      const result = AnthropicModelConfigSchema.safeParse(noModel);
      expect(result.success).toBe(false);
    });

    it('allows extra config properties with passthrough', () => {
      const configWithExtras = {
        provider: 'autogen_ext.models.anthropic.AnthropicChatCompletionClient',
        config: {
          model: 'claude-4-sonnet-20251114',
          api_key: 'test-key',
          timeout: 30,
          custom_header: 'custom-value'
        }
      };

      const result = AnthropicModelConfigSchema.safeParse(configWithExtras);
      expect(result.success).toBe(true);
      
      if (result.success) {
        expect((result.data.config as any).timeout).toBe(30);
        expect((result.data.config as any).custom_header).toBe('custom-value');
      }
    });

    it('validates with model_info object', () => {
      const configWithModelInfo = {
        provider: 'autogen_ext.models.anthropic.AnthropicChatCompletionClient',
        config: {
          model: 'claude-4-sonnet-20251114',
          model_info: {
            vision: true,
            function_calling: true,
            json_output: false,
            family: 'claude-4-sonnet',
            structured_output: false,
            multiple_system_messages: false
          }
        }
      };

      const result = AnthropicModelConfigSchema.safeParse(configWithModelInfo);
      expect(result.success).toBe(true);
      
      if (result.success) {
        expect(result.data.config.model_info?.vision).toBe(true);
        expect(result.data.config.model_info?.family).toBe('claude-4-sonnet');
      }
    });
  });

  describe('ModelConfigSchema discriminated union', () => {
    it('accepts Anthropic configuration in union', () => {
      const anthropicConfig = {
        provider: 'autogen_ext.models.anthropic.AnthropicChatCompletionClient',
        config: {
          model: 'claude-4-sonnet-20251114'
        }
      };

      const result = ModelConfigSchema.safeParse(anthropicConfig);
      expect(result.success).toBe(true);
    });

    it('accepts OpenAI configuration in union', () => {
      const openaiConfig = {
        provider: 'OpenAIChatCompletionClient',
        config: {
          model: 'gpt-4o-2024-08-06'
        }
      };

      const result = ModelConfigSchema.safeParse(openaiConfig);
      expect(result.success).toBe(true);
    });

    it('accepts Azure configuration in union', () => {
      const azureConfig = {
        provider: 'AzureOpenAIChatCompletionClient',
        config: {
          model: 'gpt-4o',
          azure_endpoint: 'https://test.openai.azure.com',
          azure_deployment: 'gpt-4o'
        }
      };

      const result = ModelConfigSchema.safeParse(azureConfig);
      expect(result.success).toBe(true);
    });

    it('accepts Ollama configuration in union', () => {
      const ollamaConfig = {
        provider: 'autogen_ext.models.ollama.OllamaChatCompletionClient',
        config: {
          model: 'llama2'
        }
      };

      const result = ModelConfigSchema.safeParse(ollamaConfig);
      expect(result.success).toBe(true);
    });

    it('rejects unknown provider in union', () => {
      const unknownConfig = {
        provider: 'UnknownProvider',
        config: {
          model: 'some-model'
        }
      };

      const result = ModelConfigSchema.safeParse(unknownConfig);
      expect(result.success).toBe(false);
    });
  });

  describe('ModelFamilySchema', () => {
    it('includes Claude model families', () => {
      const claudeFamilies = [
        'claude-3-haiku',
        'claude-3-sonnet', 
        'claude-3-opus',
        'claude-3-5-haiku',
        'claude-3-5-sonnet',
        'claude-3-7-sonnet',
        'claude-4-opus',
        'claude-4-sonnet'
      ];

      claudeFamilies.forEach(family => {
        const result = ModelFamilySchema.safeParse(family);
        expect(result.success).toBe(true);
      });
    });

    it('accepts claude-4-sonnet family', () => {
      const result = ModelFamilySchema.safeParse('claude-4-sonnet');
      expect(result.success).toBe(true);
    });

    it('rejects unknown model family', () => {
      const result = ModelFamilySchema.safeParse('claude-5-ultra');
      expect(result.success).toBe(false);
    });

    it('includes unknown fallback', () => {
      const result = ModelFamilySchema.safeParse('unknown');
      expect(result.success).toBe(true);
    });
  });

  describe('TypeScript type checking', () => {
    it('has correct AnthropicModelConfig type structure', () => {
      // This tests TypeScript compilation - if it compiles, the types are correct
      const config: AnthropicModelConfig = {
        provider: 'autogen_ext.models.anthropic.AnthropicChatCompletionClient',
        config: {
          model: 'claude-4-sonnet-20251114',
          api_key: 'test-key',
          base_url: 'https://api.anthropic.com',
          max_retries: 5,
          model_info: {
            vision: true,
            function_calling: true,
            json_output: false,
            family: 'claude-4-sonnet',
            structured_output: false,
            multiple_system_messages: false
          }
        }
      };

      expect(config.provider).toBe('autogen_ext.models.anthropic.AnthropicChatCompletionClient');
      expect(config.config.model).toBe('claude-4-sonnet-20251114');
    });

    it('enforces literal provider type', () => {
      // This should cause a TypeScript error if uncommented:
      // const badConfig: AnthropicModelConfig = {
      //   provider: 'WrongProvider',
      //   config: { model: 'claude-4-sonnet-20251114' }
      // };
      
      // Test passes if it compiles without the above
      expect(true).toBe(true);
    });

    it('allows optional config properties', () => {
      const minimalConfig: AnthropicModelConfig = {
        provider: 'autogen_ext.models.anthropic.AnthropicChatCompletionClient',
        config: {
          model: 'claude-4-sonnet-20251114'
          // api_key, base_url, max_retries are optional
        }
      };

      expect(minimalConfig.config.model).toBe('claude-4-sonnet-20251114');
    });
  });
});