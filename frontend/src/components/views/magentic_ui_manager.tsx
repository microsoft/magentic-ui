import React from "react";
import { useTranslation } from "react-i18next";

export const MagenticUIManager: React.FC = () => {
  const { t } = useTranslation();
  return <div className="relative flex h-full w-full">{t("header.title")} component</div>;
};

export default MagenticUIManager;