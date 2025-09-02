import React, { useState, useEffect, useContext, useRef } from "react";
import { Spin, message, Button, Input, Tooltip } from "antd";
import {
  PlusOutlined,
  UploadOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { appContext } from "../../../hooks/provider";
import { PlanAPI, SessionAPI } from "../../views/api";
import PlanCard from "./PlanCard";
import { IPlan } from "../../types/plan";
import { Session } from "../../types/datamodel";

interface PlanListProps {
  onTabChange?: (tabId: string) => void;
  onSelectSession?: (selectedSession: Session) => Promise<void>;
  onCreateSessionFromPlan?: (
    sessionId: number,
    sessionName: string,
    planData: IPlan
  ) => void;
}

const normalizePlanData = (
  planData: any,
  userId: string,
  defaultTask: string = "Untitled",
  preserveId: boolean = false // Add this parameter
): Partial<IPlan> => {
  return {
    // Only include ID if preserveId is true
    ...(preserveId && planData.id ? { id: planData.id } : {}),

    task: planData.task || defaultTask,
    steps: Array.isArray(planData.steps)
      ? planData.steps.map((step: any) => ({
          title: step.title || "Untitled Step",
          details: step.details || "",
          enabled: step.enabled !== false,
          open: step.open || false,
          agent_name: step.agent_name || "",
        }))
      : [],
    user_id: planData.user_id || userId,
    session_id: planData.session_id || null,
  };
};

const PlanList: React.FC<PlanListProps> = ({
  onTabChange,
  onSelectSession,
  onCreateSessionFromPlan,
}) => {
  const [plans, setPlans] = useState<IPlan[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const { user } = useContext(appContext);
  const planAPI = new PlanAPI();
  const sessionAPI = new SessionAPI();
  const [isCreatingPlan, setIsCreatingPlan] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [newPlanId, setNewPlanId] = useState<number | null>(null);
  const { t } = useTranslation();

  const userId = user?.email || "";

  const fetchPlans = async () => {
    try {
      setLoading(true);
      const response = await planAPI.listPlans(userId);

      const validatedPlans: IPlan[] = response.map(
        (plan) => normalizePlanData(plan, userId, "Untitled", true) as IPlan // preserve ID
      );

      setPlans(validatedPlans);
    } catch (err) {
      console.error("Error fetching plans:", err);
      setError(
        `${t('plans.errorOccurred')}: ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.email) {
      fetchPlans();
    } else {
      setLoading(false);
      setError(t('plans.pleaseSignIn'));
    }
  }, [user?.email]);

  const handleDeletePlan = (planId: number) => {
    setPlans((prevPlans) => prevPlans.filter((plan) => plan.id !== planId));
    message.success(t('plans.planDeletedSuccessfully'));
  };

  const handlePlanSaved = (updatedPlan: IPlan) => {
    setPlans((prevPlans) =>
      prevPlans.map((p) => (p.id === updatedPlan.id ? updatedPlan : p))
    );

    fetchPlans();
  };

  const handleUsePlan = async (plan: IPlan) => {
    try {
      message.loading({
        content: t('plans.creatingNewSession'),
        key: "sessionCreation",
      });

      const sessionResponse = await sessionAPI.createSession(
        {
          name: `${t('plans.planPrefix')}: ${plan.task}`,
          team_id: undefined, // TODO: remove team_id if not needed
        },
        userId
      );

      if (onCreateSessionFromPlan && sessionResponse.id) {
        onCreateSessionFromPlan(sessionResponse.id, `${t('plans.planPrefix')}: ${plan.task}`, plan);
      }
    } catch (error) {
      console.error("Error using plan:", error);
      message.error({
        content: t('plans.errorCreatingSession'),
        key: "sessionCreation",
      });
    }
  };

  const handleCreatePlan = async () => {
    try {
      setIsCreatingPlan(true);

      const newPlan = normalizePlanData(
        { task: t('plans.newPlan'), steps: [] },
        userId
      );

      const response = await planAPI.createPlan(newPlan, userId);

      if (response && response.id) {
        message.success(t('plans.newPlanCreatedSuccessfully'));
        setNewPlanId(response.id); // Store the new plan ID
        fetchPlans(); // Refresh the list to include the new plan
      }
    } catch (err) {
      console.error("Error creating new plan:", err);
      message.error(
        `${t('plans.failedToCreatePlan')}: ${
          err instanceof Error ? err.message : String(err)
        }`
      );
    } finally {
      setIsCreatingPlan(false);
    }
  };

  const handleImportPlan = async (file: File) => {
    try {
      const fileContent = await file.text();
      let planData;

      try {
        planData = JSON.parse(fileContent);
      } catch (parseError) {
        message.error({
          content: t('plans.invalidJsonFormat'),
          duration: 5,
        });
        return;
      }

      if (!planData || typeof planData !== "object") {
        message.error({
          content: t('plans.invalidPlanFormat'),
          duration: 5,
        });
        return;
      }

      const newPlan = normalizePlanData(planData, userId, t('plans.importedPlan'));

      const response = await planAPI.createPlan(newPlan, userId);

      if (response && response.id) {
        message.success(t('plans.planImportedSuccessfully'));
        fetchPlans(); // Refresh to get the new plan with its ID
      }
    } catch (err) {
      console.error("Error importing plan:", err);
      message.error({
        content: `${t('plans.failedToImportPlan')}: ${
          err instanceof Error ? err.message : String(err)
        }`,
        duration: 5,
      });
    }
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      handleImportPlan(files[0]);
    }
    // Reset the input so the same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (file.type === "application/json" || file.name.endsWith(".json")) {
        handleImportPlan(file);
      } else {
        message.error(t('plans.pleaseUploadJsonFile'));
      }
    }
  };

  // Filter plans based on search term
  const filteredPlans = plans.filter((plan) =>
    plan.task.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spin size="large" tip={t('plans.loadingPlans')} />
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
          {t('common.retry')}
        </button>
      </div>
    );
  }

  return (
    <div
      className="container mx-auto p-4 h-[calc(100vh-150px)] overflow-auto"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      style={{
        border: isDragging
          ? "2px dashed var(--color-primary)"
          : "2px dashed transparent",
        transition: "border 0.2s ease",
        position: "relative",
      }}
    >
      {isDragging && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10,
            pointerEvents: "none",
          }}
        >
          <div className="text-xl font-semibold text-primary">
            {t('plans.dropPlanFileHere')}
          </div>
        </div>
      )}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">{t('plans.yourSavedPlans')}</h1>
        <div className="flex items-center gap-2 w-1/3">
          <Tooltip title={t('plans.createNewEmptyPlan')}>
            <Button
              icon={<PlusOutlined />}
              onClick={handleCreatePlan}
              className="flex items-center"
            >
              {t('plans.create')}
            </Button>
          </Tooltip>
          <Tooltip title={t('plans.importPlanFromJson')}>
            <Button
              icon={<UploadOutlined />}
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center"
            >
              {t('plans.import')}
            </Button>
          </Tooltip>
          <Input
            placeholder={t('plans.searchPlans')}
            prefix={<SearchOutlined className="text-primary" />}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="rounded-md"
            allowClear
          />
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".json"
            style={{ display: "none" }}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredPlans.length > 0 ? (
          filteredPlans.map((plan) => (
            <div key={plan.id} className="h-full">
              <PlanCard
                plan={plan}
                onUsePlan={handleUsePlan}
                onPlanSaved={handlePlanSaved}
                onDeletePlan={handleDeletePlan}
                isNew={plan.id === newPlanId}
                onEditComplete={() => setNewPlanId(null)}
              />
            </div>
          ))
        ) : searchTerm ? (
          <div className="col-span-3 flex flex-col items-center justify-center py-12 text-primary">
            <SearchOutlined
              style={{ fontSize: "48px", marginBottom: "16px" }}
            />
            <p>{t('plans.noPlansFoundMatching', { searchTerm })}</p>
            <Button
              type="link"
              onClick={() => setSearchTerm("")}
              className="mt-2"
            >
              {t('plans.clearSearch')}
            </Button>
          </div>
        ) : (
          <div className="col-span-3 flex flex-col items-center justify-center py-12 text-primary">
            <p>{t('plans.noPlansYet')}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default PlanList;
