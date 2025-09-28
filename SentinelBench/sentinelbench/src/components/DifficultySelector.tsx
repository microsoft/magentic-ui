import { useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { ComponentType } from "react";

interface DifficultyVariant {
  path: string;
  title: string;
  component: ComponentType;
  password: string;
  difficulty?: "easy" | "medium" | "hard";
  dimensions?: {
    duration: string;
    criteria: string;
    activity: string;
    distraction: string;
    realism: string;
    relative_vs_absolute: string;
    adversarial_attacks: boolean;
  };
}

interface DifficultySelectorProps {
  isOpen: boolean;
  onClose: () => void;
  taskTitle: string;
  taskIcon: string;
  variants: DifficultyVariant[];
}

const DifficultySelector = ({ 
  isOpen, 
  onClose, 
  taskTitle, 
  taskIcon, 
  variants 
}: DifficultySelectorProps) => {
  const navigate = useNavigate();

  // Handle ESC key press
  useEffect(() => {
    const handleEscapeKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscapeKey);
    }

    return () => {
      document.removeEventListener('keydown', handleEscapeKey);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleVariantSelect = (variantPath: string) => {
    navigate(`/${variantPath}`);
    onClose();
  };

  // Handle click outside the modal
  const handleBackdropClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{taskIcon}</span>
            <h2 className="text-xl font-semibold text-gray-900">{taskTitle}</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl"
          >
            ×
          </button>
        </div>
        
        <p className="text-gray-600 mb-6">Choose difficulty:</p>
        
        <div className="space-y-3">
          {variants.map((variant) => (
            <button
              key={variant.path}
              onClick={() => handleVariantSelect(variant.path)}
              className="w-full p-4 text-left border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all duration-150 group"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-900 group-hover:text-blue-700">
                  {variant.title}
                </span>
                <span className="text-gray-400 group-hover:text-blue-500">
                  →
                </span>
              </div>
            </button>
          ))}
        </div>
        
        <div className="mt-6 pt-4 border-t border-gray-100">
          <p className="text-sm text-gray-500 text-center">
            Each variant maintains separate progress and has unique themes
          </p>
        </div>
      </div>
    </div>
  );
};

export default DifficultySelector;