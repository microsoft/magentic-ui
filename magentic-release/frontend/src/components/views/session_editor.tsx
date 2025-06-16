import React, { useContext, useEffect, useState } from "react";
import { Modal, Form, message, Input, Button } from "antd";
import type { FormProps } from "antd";
import { SessionEditorProps } from "./types";
import { Team } from "../types/datamodel";
import { teamAPI } from "./api";
import { appContext } from "../../hooks/provider";

type FieldType = {
  name: string;
  team_id?: number;
};

export const SessionEditor: React.FC<SessionEditorProps> = ({
  session,
  onSave,
  onCancel,
  isOpen,
}) => {
  const [form] = Form.useForm();
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(false);
  const { user } = useContext(appContext);
  const [messageApi, contextHolder] = message.useMessage();

  const getDefaultSessionName = () => {
    const today = new Date();
    return today.toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Fetch teams when modal opens
  useEffect(() => {
    const fetchTeams = async () => {
      if (isOpen) {
        try {
          setLoading(true);
          const userId = user?.email || "";
          const teamsData = await teamAPI.listTeams(userId);
          setTeams(teamsData);
        } catch (error) {
          messageApi.error("Error loading teams");
          console.error("Error loading teams:", error);
        } finally {
          setLoading(false);
        }
      }
    };

    fetchTeams();
  }, [isOpen, user?.email]);

  // Set form values when modal opens or session changes
  useEffect(() => {
    if (isOpen) {
      form.setFieldsValue({
        name: session?.name || getDefaultSessionName(),
        team_id: session?.team_id || undefined,
      });
    } else {
      form.resetFields();
    }
  }, [form, session, isOpen]);

  const onFinish: FormProps<FieldType>["onFinish"] = async (values: any) => {
    try {
      await onSave({
        ...values,
        id: session?.id,
      });
      messageApi.success(
        `Session ${session ? "updated" : "created"} successfully`
      );
    } catch (error) {
      if (error instanceof Error) {
        messageApi.error(error.message);
      }
    }
  };

  const onFinishFailed: FormProps<FieldType>["onFinishFailed"] = (
    errorInfo: any
  ) => {
    messageApi.error("Please check the form for errors");
    console.error("Form validation failed:", errorInfo);
  };

  const hasNoTeams = false;

  return (
    <Modal
      title={session ? "Edit Session" : "Create Session"}
      open={isOpen}
      onCancel={onCancel}
      footer={null}
      className="text-primary"
      forceRender
    >
      {contextHolder}
      <Form
        form={form}
        name="session-form"
        layout="vertical"
        onFinish={onFinish}
        onFinishFailed={onFinishFailed}
        autoComplete="off"
      >
        <Form.Item<FieldType>
          label="Session Name"
          name="name"
          rules={[
            { required: true, message: "Please enter a session name" },
            { max: 100, message: "Session name cannot exceed 100 characters" },
          ]}
        >
          <Input />
        </Form.Item>

        <Form.Item className="flex justify-end mb-0">
          <div className="flex gap-2">
            <Button onClick={onCancel}>Cancel</Button>
            <Button type="primary" htmlType="submit" disabled={hasNoTeams}>
              {session ? "Update" : "Create"}
            </Button>
          </div>
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default SessionEditor;
