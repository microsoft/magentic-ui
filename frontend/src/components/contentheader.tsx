import React from "react";
import { PanelLeftClose, PanelLeftOpen, Plus } from "lucide-react";
import { Tooltip } from "antd";
import { appContext } from "../hooks/provider";
import { useConfigStore } from "../hooks/store";
import { Settings } from "lucide-react";
import SignInModal from "./signin";
import SettingsModal from "./settings/SettingsModal";
import logo from "../assets/logo.svg";
import { Button } from "./common/Button";

type ContentHeaderProps = {
  onMobileMenuToggle: () => void;
  isMobileMenuOpen: boolean;
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  onNewSession: () => void;
};

const ContentHeader = ({
  isSidebarOpen,
  onToggleSidebar,
  onNewSession,
}: ContentHeaderProps) => {
  const { user } = React.useContext(appContext);
  useConfigStore();
  const [isEmailModalOpen, setIsEmailModalOpen] = React.useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = React.useState(false);

  return (
    <div className="sticky top-0 bg-primary">
      <div className="flex h-16 items-center justify-between pr-4 sm:pr-6 md:pr-8">
        {/* Left side: Logo and Title (aligned with sidebar) */}
        <div className="flex items-center gap-2">
          <div className="flex w-[360px] items-center">
            <div className="flex items-center gap-3 px-3">
              <img
                src={logo}
                alt="Magentic-UI Logo"
                className="h-[55px] w-[55px]"
              />
              <div className="text-[20px] font-semibold text-primary">
                Magentic-UI
              </div>
            </div>

            {/* Sidebar closed: show new session button */}
            {!isSidebarOpen && (
              <Tooltip title="Create new session">
                <Button
                  variant="tertiary"
                  size="sm"
                  icon={<Plus className="h-6 w-6" />}
                  onClick={onNewSession}
                  className="transition-colors hover:text-accent"
                />
              </Tooltip>
            )}

            {/* Sidebar Toggle - aligned to right edge of sidebar */}
            <div className="ml-auto pr-3">
              <Tooltip title={isSidebarOpen ? "Close Sidebar" : "Open Sidebar"}>
                <Button
                  variant="tertiary"
                  size="sm"
                  icon={
                    isSidebarOpen ? (
                      <PanelLeftClose strokeWidth={1.5} className="h-6 w-6" />
                    ) : (
                      <PanelLeftOpen strokeWidth={1.5} className="h-6 w-6" />
                    )
                  }
                  onClick={onToggleSidebar}
                  className="!px-0 transition-colors hover:text-accent"
                />
              </Tooltip>
            </div>
          </div>
        </div>

        {/* User Profile and Settings */}
        <div className="flex items-center space-x-4">
          {/* User Profile */}
          {user && (
            <Tooltip title="View or update your profile">
              <div
                className="flex cursor-pointer items-center space-x-2"
                onClick={() => setIsEmailModalOpen(true)}
              >
                {user.avatar_url ? (
                  <img
                    className="h-8 w-8 rounded-full"
                    src={user.avatar_url}
                    alt={user.name}
                  />
                ) : (
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-400 font-semibold text-gray-800 hover:text-message">
                    {user.name?.[0]}
                  </div>
                )}
              </div>
            </Tooltip>
          )}

          {/* Settings Button */}
          <div className="text-primary">
            <Tooltip title="Settings">
              <Button
                variant="tertiary"
                size="sm"
                icon={<Settings className="h-8 w-8" />}
                onClick={() => setIsSettingsOpen(true)}
                className="!px-0 transition-colors hover:text-accent"
                aria-label="Settings"
              />
            </Tooltip>
          </div>
        </div>
      </div>

      <SignInModal
        isVisible={isEmailModalOpen}
        onClose={() => setIsEmailModalOpen(false)}
      />
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
};

export default ContentHeader;
