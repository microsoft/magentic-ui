import * as React from "react";
import { appContext } from "../hooks/provider";
import { useConfigStore } from "../hooks/store";
import "antd/dist/reset.css";
import { ConfigProvider, theme } from "antd";
import { SessionManager } from "./views/manager";
import { useTranslation } from "react-i18next";

const classNames = (...classes: (string | undefined | boolean)[]) => {
  return classes.filter(Boolean).join(" ");
};

type Props = {
  title: string;
  link: string;
  children?: React.ReactNode;
  showHeader?: boolean;
  restricted?: boolean;
  meta?: any;
  activeTab?: string;
  onTabChange?: (tab: string) => void;
};

const MagenticUILayout = ({
  meta,
  title,
  link,
  showHeader = true,
  restricted = false,
  activeTab,
  onTabChange,
}: Props) => {
  const { darkMode, user, setUser } = React.useContext(appContext);
  const { sidebar } = useConfigStore();
  const { isExpanded } = sidebar;
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);
  const { t } = useTranslation();

  // Mimic sign-in: if no user or user.email, set default user and localStorage
  React.useEffect(() => {
    if (!user?.email) {
      const defaultEmail = "default";
      setUser({ ...user, email: defaultEmail, name: defaultEmail });
      if (typeof window !== "undefined") {
        window.localStorage.setItem("user_email", defaultEmail);
      }
    }
  }, [user, setUser]);

  // Close mobile menu on route change
  React.useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [link]);

  React.useEffect(() => {
    document.getElementsByTagName("html")[0].className = `${
      darkMode === "dark" ? "dark bg-primary" : darkMode === "light" ? "light bg-primary" : "spirits bg-primary"
    }`;
  }, [darkMode]);

  const layoutContent = (
    <div className="h-screen flex">
      {/* Content area */}
      <div
        className={classNames(
          "flex-1 flex flex-col min-h-screen",
          "transition-all duration-300 ease-in-out",
          "md:pl-1",
          isExpanded ? "md:pl-1" : "md:pl-1"
        )}
      >
        <ConfigProvider
          theme={{
            token: {
              borderRadius: 4,
              colorBgBase: darkMode === "dark" ? "#2a2a2a" : darkMode === "light" ? "#ffffff" : "#f6f7fa",
            },
            algorithm:
              darkMode === "dark"
                ? theme.darkAlgorithm
                : theme.defaultAlgorithm,
          }}
        >
          <main className="flex-1 p-1 text-primary" style={{ height: "100%" }}>
            <SessionManager />
          </main>
        </ConfigProvider>
        <div className="text-sm text-primary mt-2 mb-2 text-center">
          {t('messages.mistakes')}
        </div>
      </div>
    </div>
  );

  if (restricted) {
    return (
      <appContext.Consumer>
        {(context: any) => {
          if (context.user) {
            return layoutContent;
          }
          return null;
        }}
      </appContext.Consumer>
    );
  }

  return layoutContent;
};

export default MagenticUILayout;
