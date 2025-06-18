import React, { ReactNode } from "react";

export interface SubMenuItemProps<T> {
  id: T;
  label: string;
  icon?: ReactNode;
}

interface SubMenuProps<T> {
  items: SubMenuItemProps<T>[];
  activeItem: T;
  onClick: (id: T) => void;
}

function SubMenu<T extends string>({
  activeItem,
  onClick,
  items,
}: SubMenuProps<T>) {
  return (
    <div className="w-full border-b border-secondary">
      {items.map((item) => (
        <button
          key={item.id}
          className={`w-full text-left py-2 pl-0 pr-4 text-sm transition-colors flex items-center
            ${
              activeItem === item.id
                ? "font-semibold text-magenta-800"
                : "font-normal text-secondary hover:text-primary"
            }`}
          onClick={() => onClick(item.id)}
        >
          {item.icon && <span className="mr-2">{item.icon}</span>}
          {item.label}
        </button>
      ))}
    </div>
  );
}

export default SubMenu;
