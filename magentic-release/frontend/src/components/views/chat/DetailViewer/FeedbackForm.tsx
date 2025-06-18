import React from "react";
import { Input } from "antd";
import { EyeOff } from "lucide-react";
import { Button } from "../../../../components/common/Button";

const { TextArea } = Input;

interface FeedbackFormProps {
  userFeedback: string;
  setUserFeedback: (feedback: string) => void;
  onSubmit: () => void;
}

const FeedbackForm: React.FC<FeedbackFormProps> = ({
  userFeedback,
  setUserFeedback,
  onSubmit,
}) => {
  return (
    <div className="fixed inset-0 flex items-center pointer-events-none">
      {/* This container controls the position */}
      <div className="w-[22vw] ml-[10vw] pointer-events-none">
        <div className="feedback-form w-full max-w-md pointer-events-auto">
          <div className="bg-tertiary rounded-lg shadow-lg p-6">
            <div className="flex justify-center mb-4">
              <div className="p-2 rounded-full bg-blue-700">
                <EyeOff className="text-blue-800 w-8 h-8" />
              </div>
            </div>
            <h3 className="text-lg font-medium text-primary mb-4 text-center">
              Magentic-UI can't see what you do when you take control.
            </h3>
            <p className="text-base mb-4 text-primary">
              Please describe what you did when you are ready to hand back
              control:
            </p>

            <TextArea
              value={userFeedback}
              onChange={(e) => setUserFeedback(e.target.value)}
              placeholder="For example: I entered my zip code, I clicked on the top link..."
              autoSize={{ minRows: 5, maxRows: 8 }}
              className="w-full text-primary placeholder:text-secondary"
            />

            <div className="mt-4">
              <Button
                variant="primary"
                size="md"
                fullWidth
                onClick={onSubmit}
                className="font-medium shadow-md"
              >
                Give control back to Magentic-UI
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FeedbackForm;
