import React, { useState } from "react";
import { getLocalStorage, setLocalStorage } from "../components/utils";
import { message } from "antd";
import { useTranslation } from "react-i18next";

export interface IUser {
  name: string;
  email?: string;
  username?: string;
  avatar_url?: string;
  metadata?: any;
}

export interface AppContextType {
  user: IUser | null;
  setUser: any;
  logout: any;
  cookie_name: string;
  darkMode: string;
  setDarkMode: any;
  language: "zh-CN" | "en-US";
  setLanguage: any;
}

const cookie_name = "coral_app_cookie_";

export const appContext = React.createContext<AppContextType>(
  {} as AppContextType
);
const Provider = ({ children }: any) => {
  const { i18n } = useTranslation();
  
  // theme config
  const storedValue = getLocalStorage("darkmode", false);
  const [darkMode, setDarkMode] = useState(
    storedValue === null ? "dark" : storedValue === "dark" ? "dark" : "light"
  );
  // language config
  const storedLanguage = getLocalStorage("language", false);
  const [language, setLanguageState] = useState<"zh-CN" | "en-US">(
    storedLanguage === null ? "zh-CN" : (storedLanguage === "zh-CN" || storedLanguage === "en-US") ? storedLanguage : "zh-CN"
  );
  const logout = () => {
    // setUser(null);
    // eraseCookie(cookie_name);
    console.log("Please implement your own logout logic");
    message.info("Please implement your own logout logic");
  };

  const updateDarkMode = (darkMode: string) => {
    setDarkMode(darkMode);
    setLocalStorage("darkmode", darkMode, false);
  };

  const updateLanguage = (language: "zh-CN" | "en-US") => {
    setLanguageState(language);
    setLocalStorage("language", language, false);
    i18n.changeLanguage(language);
  };

  // 初始化语言
  React.useEffect(() => {
    i18n.changeLanguage(language);
  }, [i18n, language]);

  // Modify logic here to add your own authentication
  const initUser = {
    name: "Guest User",
    email: getLocalStorage("user_email") || "guestuser@gmail.com",
    username: "guestuser",
  };

  const setUser = (user: IUser | null) => {
    if (user?.email) {
      setLocalStorage("user_email", user.email, false);
    }
    setUserState(user);
  };

  const [userState, setUserState] = useState<IUser | null>(initUser);

  React.useEffect(() => {
    const storedEmail = getLocalStorage("user_email");
    if (storedEmail) {
      setUserState((prevUser) => ({
        ...prevUser,
        email: storedEmail,
        name: storedEmail,
      }));
    }
  }, []);

  return (
    <appContext.Provider
      value={{
        user: userState,
        setUser,
        logout,
        cookie_name,
        darkMode,
        setDarkMode: updateDarkMode,
        language,
        setLanguage: updateLanguage,
      }}
    >
      {children}
    </appContext.Provider>
  );
};

export default ({ element }: any) => <Provider>{element}</Provider>;
