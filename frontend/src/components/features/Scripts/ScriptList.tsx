import React, { useState, useEffect, useContext } from "react";
import { Spin, message, Input } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { appContext } from "../../../hooks/provider";
import { ScriptAPI, SessionAPI } from "../../views/api";
import ScriptCard, { IScript } from "./ScriptCard";
import { Session } from "../../types/datamodel";

interface ScriptListProps {
  onTabChange?: (tabId: string) => void;
  onSelectSession?: (selectedSession: Session) => Promise<void>;
  onCreateSessionFromScript?: (
    sessionId: number,
    sessionName: string,
    scriptData: IScript
  ) => void;
}

const ScriptList: React.FC<ScriptListProps> = ({
  onTabChange,
  onSelectSession,
  onCreateSessionFromScript,
}) => {
  const [scripts, setScripts] = useState<IScript[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const { user } = useContext(appContext);
  const scriptAPI = new ScriptAPI();
  const sessionAPI = new SessionAPI();
  const [searchTerm, setSearchTerm] = useState<string>("");
  const { t } = useTranslation();

  const userId = user?.email || "";

  const fetchScripts = async () => {
    try {
      setLoading(true);
      const response = await scriptAPI.listScripts(userId);
      setScripts(response || []);
    } catch (err) {
      console.error("Error fetching scripts:", err);
      setError(
        `${t("scripts.errorOccurred")}: ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.email) {
      fetchScripts();
    } else {
      setLoading(false);
      setError(t("scripts.pleaseSignIn"));
    }
  }, [user?.email]);

  const handleDeleteScript = (scriptId: number) => {
    setScripts((prevScripts) => prevScripts.filter((s) => s.id !== scriptId));
    message.success(t("scripts.scriptDeletedSuccessfully"));
  };

  const handleRunScript = async (script: IScript) => {
    try {
      message.loading({
        content: t("scripts.creatingNewSession"),
        key: "sessionCreation",
      });

      const sessionResponse = await sessionAPI.createSession(
        {
          name: `${t("scripts.scriptPrefix")}: ${script.task}`,
          team_id: undefined,
        },
        userId
      );

      if (onCreateSessionFromScript && sessionResponse.id) {
        onCreateSessionFromScript(
          sessionResponse.id,
          `${t("scripts.scriptPrefix")}: ${script.task}`,
          script
        );
      }

      message.success({
        content: t("scripts.scriptStarted"),
        key: "sessionCreation",
      });
    } catch (error) {
      console.error("Error running script:", error);
      message.error({
        content: t("scripts.errorCreatingSession"),
        key: "sessionCreation",
      });
    }
  };

  // Filter scripts based on search term
  const filteredScripts = scripts.filter((script) =>
    (script.task || "").toLowerCase().includes(searchTerm.toLowerCase()) ||
    (script.start_url || "").toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spin size="large" tip={t("scripts.loadingScripts")} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center p-8 text-red-500">
        <p>{error}</p>
        <button
          className="mt-4 px-4 py-2 bg-primary text-white rounded hover:bg-primary/80"
          onClick={() => window.location.reload()}
        >
          {t("common.retry")}
        </button>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4 h-[calc(100vh-150px)] overflow-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">{t("scripts.yourSavedScripts")}</h1>
        <div className="flex items-center gap-2 w-1/3">
          <Input
            placeholder={t("scripts.searchScripts")}
            prefix={<SearchOutlined className="text-primary" />}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="rounded-md"
            allowClear
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredScripts.length > 0 ? (
          filteredScripts.map((script) => (
            <div key={script.id} className="h-full">
              <ScriptCard
                script={script}
                onRunScript={handleRunScript}
                onDeleteScript={handleDeleteScript}
              />
            </div>
          ))
        ) : searchTerm ? (
          <div className="col-span-3 flex flex-col items-center justify-center py-12 text-primary">
            <SearchOutlined style={{ fontSize: "48px", marginBottom: "16px" }} />
            <p>{t("scripts.noScriptsFoundMatching", { searchTerm })}</p>
            <button
              className="mt-2 text-blue-500 hover:underline"
              onClick={() => setSearchTerm("")}
            >
              {t("scripts.clearSearch")}
            </button>
          </div>
        ) : (
          <div className="col-span-3 flex flex-col items-center justify-center py-12 text-primary">
            <p>{t("scripts.noScriptsYet")}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ScriptList;
