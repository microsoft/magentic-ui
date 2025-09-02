import React, { useCallback } from "react";
import { Input, message } from "antd";

const { TextArea } = Input;

interface JsonFormProps {
  value: string;
  onValueChanged: (value: string) => void;
}

const JsonForm: React.FC<JsonFormProps> = ({ value, onValueChanged }) => {
  const validateAndParseJson = (content: string) => {
    try {
      const parsed = JSON.parse(content);
      if (!parsed.server_name) {
        throw new Error("Missing required field: server_name");
      }

      return parsed;
    } catch (error) {
      throw new Error(`Invalid JSON configuration: ${error instanceof Error ? error.message : 'Invalid JSON format'}`);
    }
  };

  const handleFileRead = useCallback((file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        const parsed = validateAndParseJson(content);
        // Format the JSON nicely for editing
        const formattedJson = JSON.stringify(parsed, null, 2);
        // Update the value through the controlled state
        onValueChanged(formattedJson);
        message.success("JSON file loaded successfully!");
      } catch (error) {
        console.error("File read error:", error);
        message.error(error instanceof Error ? error.message : "Failed to parse JSON file");
      }
    };
    reader.readAsText(file);
  }, [onValueChanged]);

  const handleTextareaDrop = useCallback((e: React.DragEvent<HTMLTextAreaElement>) => {
    e.preventDefault();
    e.stopPropagation();

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (file.type === 'application/json' || file.name.endsWith('.json')) {
        handleFileRead(file);
      } else {
        message.error('Please upload a valid JSON file');
      }
    }
  }, [handleFileRead]);

  const handleTextareaDragOver = useCallback((e: React.DragEvent<HTMLTextAreaElement>) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  return (
    <div className="space-y-2">
      {/* JSON Editor */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          JSON Configuration
        </label>
        <TextArea
          rows={6}
          value={value}
          placeholder={`{
            "server_name": "my-server",
            "server_params": {
              "type": "StdioServerParams",
              "command": "npx",
              "args": ["@modelcontextprotocol/server-filesystem"],
              "read_timeout_seconds": 5
            }
          }`}
          onChange={(e) => onValueChanged(e.target.value)}
          onDrop={handleTextareaDrop}
          onDragOver={handleTextareaDragOver}
          className="cursor-text"
        />
        <p className="text-sm text-gray-500 mt-1">
          Drag and drop a JSON file directly onto the textarea, or paste JSON content.
        </p>
      </div>
    </div>
  );
};

export default JsonForm;
