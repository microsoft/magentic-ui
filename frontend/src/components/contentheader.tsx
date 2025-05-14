import React from "react";
import { PanelLeftClose, PanelLeftOpen, Plus } from "lucide-react";
import { Tooltip, Button } from "antd";
import { appContext } from "../hooks/provider";
import { useConfigStore } from "../hooks/store";
import { Settings } from "lucide-react";
import SignInModal from "./signin";
import SettingsMenu from "./settings";
import logo from "../assets/logo.svg";

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
      <div className="flex h-16 items-center justify-between">
        {/* Left side: Text and Sidebar Controls */}
        <div className="flex items-center">
          {/* Sidebar Toggle */}
          <Tooltip title={isSidebarOpen ? "Close Sidebar" : "Open Sidebar"}>
            <button
              onClick={onToggleSidebar}
              className="rounded-md hover:bg-secondary hover:text-accent text-secondary transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-opacity-50"
            >
              {isSidebarOpen ? (
                <PanelLeftClose strokeWidth={1.5} className="h-6 w-6" />
              ) : (
                <PanelLeftOpen strokeWidth={1.5} className="h-6 w-6" />
              )}
            </button>
          </Tooltip>

          {/* New Session Button */}
          <div className="w-[40px]">
            {!isSidebarOpen && (
              <Tooltip title="Create new session">
                <Button
                  type="text"
                  className="flex items-center justify-center hover:text-accent"
                  onClick={onNewSession}
                  icon={<Plus className="w-5 h-5" />}
                ></Button>
              </Tooltip>
            )}
          </div>
          <div className="flex items-center space-x-2">
            <img src={logo} alt="Magentic-UI Logo" className="h-10 w-10" />
            <div className="text-primary text-2xl font-bold">Magentic-UI</div>
          </div>
        </div>

        {/* User Profile and Settings */}
        <div className="flex items-center space-x-4">
          {/* User Profile */}
          {user && (
            <Tooltip title="View or update your profile">
              <div
                className="flex items-center space-x-2 cursor-pointer"
                onClick={() => setIsEmailModalOpen(true)}
              >
                {user.avatar_url ? (
                  <img
                    className="h-8 w-8 rounded-full"
                    src={user.avatar_url}
                    alt={user.name}
                  />
                ) : (
                  <div className="border-2 bg-accent h-8 w-8 rounded-full flex items-center justify-center text-white">
                    {user.name?.[0]}
                  </div>
                )}
              </div>
            </Tooltip>
          )}

          {/* Settings Button */}
          <div className="text-primary">
            <Tooltip title="Settings">
              <button
                onClick={() => setIsSettingsOpen(true)}
                className="hover:text-accent transition-colors p-2"
                aria-label="Settings"
              >
                <Settings className="h-6 w-6" />
              </button>
            </Tooltip>
          </div>
        </div>
      </div>

      <SignInModal
        isVisible={isEmailModalOpen}
        onClose={() => setIsEmailModalOpen(false)}
      />
      <SettingsMenu
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
};

export default ContentHeader;
