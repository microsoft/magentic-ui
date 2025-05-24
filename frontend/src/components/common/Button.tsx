import React from "react";
import { Spin } from "antd";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "tertiary"
  | "success"
  | "warning"
  | "danger";
export type ButtonSize = "xs" | "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  icon?: React.ReactNode;
  iconPosition?: "left" | "right";
  fullWidth?: boolean;
  children?: React.ReactNode;
  className?: string;
}

export const Button: React.FC<ButtonProps> = ({
  variant = "primary",
  size = "md",
  isLoading = false,
  icon,
  iconPosition = "left",
  fullWidth = false,
  disabled = false,
  children,
  className = "",
  ...props
}) => {
  // Base classes shared by all buttons
  const baseClasses =
    "inline-flex items-center justify-center rounded-md transition-colors focus:outline-none";

  // Size variations
  const sizeClasses = {
    xs: "px-2 py-1 text-xs",
    sm: "px-2.5 py-1.5 text-sm",
    md: "px-4 py-2 text-base",
    lg: "px-6 py-3 text-lg",
  };

  // Variant classes - these would use your color variables
  const variantClasses = {
    primary:
      "bg-magenta-800 text-white hover:bg-magenta-900 focus:ring-2 focus:ring-magenta-900",
    secondary:
      "bg-transparent border border-magenta-800 text-magenta-800 hover:bg-magenta-900/50",
    tertiary: "bg-transparent text-gray-800 hover:text-primary",
    success:
      "bg-green-600 text-white hover:bg-green-700 focus:ring-2 focus:ring-green-400",
    warning:
      "bg-warning-primary text-white hover:bg-amber-600 focus:ring-2 focus:ring-amber-400",
    danger:
      "bg-red-600 text-white hover:bg-red-700 focus:ring-2 focus:ring-red-400",
  };

  // States
  const stateClasses =
    disabled || isLoading ? "opacity-60 cursor-not-allowed" : "cursor-pointer";

  // Width
  const widthClass = fullWidth ? "w-full" : "";

  return (
    <button
      disabled={disabled || isLoading}
      className={`
        ${baseClasses}
        ${sizeClasses[size]}
        ${variantClasses[variant]}
        ${stateClasses}
        ${widthClass}
        ${className}
      `}
      {...props}
    >
      {isLoading && <Spin size="small" className={children ? "mr-2" : ""} />}

      {!isLoading && icon && iconPosition === "left" && (
        <span className={`${children ? "mr-2" : ""}`}>{icon}</span>
      )}

      {children}

      {!isLoading && icon && iconPosition === "right" && (
        <span className={`${children ? "ml-2" : ""}`}>{icon}</span>
      )}
    </button>
  );
};
