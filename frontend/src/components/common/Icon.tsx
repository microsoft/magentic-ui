import React, { useId } from "react";
import { Bot, Code, Folder, Globe, User } from "lucide-react";

interface IconProps {
  className?: string;
  size?: number;
  tooltip?: string;
}

const IconWrapper: React.FC<IconProps & { children: React.ReactNode }> = ({
  className = "",
  size = 16,
  tooltip,
  children
}) => {
  const uniqueId = useId();
  const groupClass = `tooltip-group-${uniqueId.replace(/:/g, '')}`;
  
  return (
    <div className={`relative ${groupClass} inline-flex`}>
      {children}
      {tooltip && (
        <style>{`
          .${groupClass}:hover .${groupClass}-tooltip {
            opacity: 1;
          }
        `}</style>
      )}
      {tooltip && (
        <div className={`${groupClass}-tooltip absolute left-1/2 -translate-x-1/2 -top-8 px-2 py-1 bg-gray-800 text-white text-sm rounded opacity-0 transition-opacity z-10`}>
          {tooltip}
        </div>
      )}
    </div>
  );
};

export const CoderIcon = ({ className = "", size = 16, tooltip }: IconProps) => (
  <IconWrapper className={className} size={size} tooltip={tooltip}>
    <Code className={className} size={size} />
  </IconWrapper>
);

export const FileSurferIcon = ({ className = "", size = 16, tooltip }: IconProps) => (
  <IconWrapper className={className} size={size} tooltip={tooltip}>
    <Folder className={className} size={size} />
  </IconWrapper>
);

export const WebSurferIcon = ({ className = "", size = 16, tooltip }: IconProps) => (
  <IconWrapper className={className} size={size} tooltip={tooltip}>
    <Globe className={className} size={size} />
  </IconWrapper>
);

export const UserIcon = ({ className = "", size = 16, tooltip }: IconProps) => (
  <IconWrapper className={className} size={size} tooltip={tooltip}>
    <User className={className} size={size} />
  </IconWrapper>
);

export const AgentIcon = ({ className = "", size = 16, tooltip }: IconProps) => (
  <IconWrapper className={className} size={size} tooltip={tooltip}>
    <Bot className={className} size={size} />
  </IconWrapper>
);
