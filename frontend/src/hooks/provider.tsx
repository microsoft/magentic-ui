import React, { useState } from "react";
import { getLocalStorage, setLocalStorage } from "../components/utils";
import { message } from "antd";

export interface IUser {
  name: string;
  email?: string;
  username?: string;
  avatar_url?: string;
  metadata?: Record<string, unknown>;
}

export interface AppContextType {
  user: IUser | null;
  setUser: (user: IUser | null) => void;
  logout: () => void;
  cookie_name: string;
  darkMode: string;
  setDarkMode: (mode: string) => void;
}

const cookie_name = "coral_app_cookie_";

export const appContext = React.createContext<AppContextType>(
  {} as AppContextType
);
const Provider = ({ children }: { children: React.ReactNode }) => {
  const storedValue = getLocalStorage("darkmode", false);
  const [darkMode, setDarkMode] = useState(
    storedValue === null ? "dark" : storedValue === "dark" ? "dark" : "light"
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

  // Modify logic here to add your own authentication
  const initUser = {
    name: "Guest User",
    email: (getLocalStorage("user_email") as string) || "guestuser@gmail.com",
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
        email: storedEmail as string,
        name: storedEmail as string,
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
      }}
    >
      {children}
    </appContext.Provider>
  );
};

const RootProvider = ({ element }: { element: React.ReactNode }) => <Provider>{element}</Provider>;
RootProvider.displayName = 'RootProvider';

export default RootProvider;
