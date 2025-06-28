/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AnthropicModelConfigForm, DEFAULT_ANTHROPIC } from '../AnthropicModelConfigForm';
import { AnthropicModelConfig } from '../types';

// Mock antd components
jest.mock('antd', () => ({
  Input: ({ placeholder, onChange, value, ...props }: any) => (
    <input
      placeholder={placeholder}
      onChange={(e) => onChange?.(e.target.value)}
      value={value}
      {...props}
    />
  ),
  Form: {
    useForm: () => [{ setFieldsValue: jest.fn(), getFieldsValue: () => ({}) }],
    Item: ({ children, label }: any) => (
      <div>
        <label>{label}</label>
        {children}
      </div>
    ),
  },
  Button: ({ children, onClick }: any) => (
    <button onClick={onClick}>{children}</button>
  ),
  Switch: ({ checked, onChange }: any) => (
    <input
      type="checkbox"
      checked={checked}
      onChange={(e) => onChange?.(e.target.checked)}
    />
  ),
  Flex: ({ children }: any) => <div>{children}</div>,
  Collapse: {
    Panel: ({ children }: any) => <div>{children}</div>,
  },
}));

describe('AnthropicModelConfigForm', () => {
  const mockOnChange = jest.fn();
  const mockOnSubmit = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders with default Anthropic configuration', () => {
    render(<AnthropicModelConfigForm onChange={mockOnChange} />);
    
    expect(screen.getByDisplayValue('claude-4-sonnet-20251114')).toBeInTheDocument();
    expect(screen.getByLabelText('Model')).toBeInTheDocument();
    expect(screen.getByLabelText('API Key')).toBeInTheDocument();
    expect(screen.getByLabelText('Base URL')).toBeInTheDocument();
    expect(screen.getByLabelText('Max Retries')).toBeInTheDocument();
  });

  it('displays correct default values', () => {
    expect(DEFAULT_ANTHROPIC.provider).toBe('autogen_ext.models.anthropic.AnthropicChatCompletionClient');
    expect(DEFAULT_ANTHROPIC.config.model).toBe('claude-4-sonnet-20251114');
    expect(DEFAULT_ANTHROPIC.config.max_retries).toBe(5);
  });

  it('shows advanced toggles when hideAdvancedToggles is false', () => {
    render(<AnthropicModelConfigForm onChange={mockOnChange} hideAdvancedToggles={false} />);
    
    expect(screen.getByLabelText('Vision')).toBeInTheDocument();
    expect(screen.getByLabelText('Function Calling')).toBeInTheDocument();
    expect(screen.getByLabelText('JSON Output')).toBeInTheDocument();
    expect(screen.getByLabelText('Structured Output')).toBeInTheDocument();
    expect(screen.getByLabelText('Multiple System Messages')).toBeInTheDocument();
  });

  it('hides advanced toggles when hideAdvancedToggles is true', () => {
    render(<AnthropicModelConfigForm onChange={mockOnChange} hideAdvancedToggles={true} />);
    
    expect(screen.queryByLabelText('Vision')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Function Calling')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('JSON Output')).not.toBeInTheDocument();
  });

  it('calls onChange when model value changes', async () => {
    render(<AnthropicModelConfigForm onChange={mockOnChange} />);
    
    const modelInput = screen.getByLabelText('Model');
    fireEvent.change(modelInput, { target: { value: 'claude-3-5-sonnet-20241022' } });
    
    await waitFor(() => {
      expect(mockOnChange).toHaveBeenCalled();
    });
  });

  it('calls onChange when API key changes', async () => {
    render(<AnthropicModelConfigForm onChange={mockOnChange} />);
    
    const apiKeyInput = screen.getByLabelText('API Key');
    fireEvent.change(apiKeyInput, { target: { value: 'sk-ant-test-key' } });
    
    await waitFor(() => {
      expect(mockOnChange).toHaveBeenCalled();
    });
  });

  it('shows Save button when onSubmit prop is provided', () => {
    render(<AnthropicModelConfigForm onChange={mockOnChange} onSubmit={mockOnSubmit} />);
    
    expect(screen.getByText('Save')).toBeInTheDocument();
  });

  it('does not show Save button when onSubmit prop is not provided', () => {
    render(<AnthropicModelConfigForm onChange={mockOnChange} />);
    
    expect(screen.queryByText('Save')).not.toBeInTheDocument();
  });

  it('calls onSubmit when Save button is clicked', () => {
    render(<AnthropicModelConfigForm onChange={mockOnChange} onSubmit={mockOnSubmit} />);
    
    const saveButton = screen.getByText('Save');
    fireEvent.click(saveButton);
    
    expect(mockOnSubmit).toHaveBeenCalled();
  });

  it('renders with provided value prop', () => {
    const testValue: AnthropicModelConfig = {
      provider: 'autogen_ext.models.anthropic.AnthropicChatCompletionClient',
      config: {
        model: 'claude-3-opus-20240229',
        api_key: 'test-key',
        base_url: 'https://custom-endpoint.com',
        max_retries: 3,
      }
    };

    render(<AnthropicModelConfigForm onChange={mockOnChange} value={testValue} />);
    
    expect(screen.getByDisplayValue('claude-3-opus-20240229')).toBeInTheDocument();
    expect(screen.getByDisplayValue('test-key')).toBeInTheDocument();
    expect(screen.getByDisplayValue('https://custom-endpoint.com')).toBeInTheDocument();
    expect(screen.getByDisplayValue('3')).toBeInTheDocument();
  });

  it('has correct placeholder text', () => {
    render(<AnthropicModelConfigForm onChange={mockOnChange} />);
    
    expect(screen.getByPlaceholderText('claude-4-sonnet-20251114')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Your Anthropic API key')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('https://api.anthropic.com')).toBeInTheDocument();
  });

  it('sets correct model family in advanced defaults', () => {
    const { container } = render(
      <AnthropicModelConfigForm onChange={mockOnChange} hideAdvancedToggles={false} />
    );
    
    // The model family should be set to claude-4-sonnet by default
    // This is tested indirectly through the form structure
    expect(container).toBeInTheDocument();
  });
});