import React from "react";
import { Input, Switch, Button, Space, Tag, Tooltip } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import { Plus } from "lucide-react";

interface AllowedWebsitesListProps {
  config: any;
  handleUpdateConfig: (changes: any) => void;
}

const AllowedWebsitesList: React.FC<AllowedWebsitesListProps> = ({
  config,
  handleUpdateConfig,
}) => {
  const [websiteInput, setWebsiteInput] = React.useState("");
  const [cachedWebsites, setCachedWebsites] = React.useState<string[]>(config.allowed_websites || []);
  const [allowedlistEnabled, setAllowedlistEnabled] = React.useState(Boolean((config.allowed_websites || []).length));

  React.useEffect(() => {
    setCachedWebsites(config.allowed_websites || []);
    setAllowedlistEnabled(Boolean((config.allowed_websites || []).length));
  }, [config.allowed_websites]);

  const addWebsite = () => {
    if (websiteInput && !cachedWebsites.includes(websiteInput)) {
      const updatedList = [...cachedWebsites, websiteInput];
      setCachedWebsites(updatedList);
      handleUpdateConfig({ allowed_websites: updatedList });
      setWebsiteInput("");
    }
  };

  const removeWebsite = (site: string) => {
    const updatedList = cachedWebsites.filter((item) => item !== site);
    setCachedWebsites(updatedList);
    handleUpdateConfig({ allowed_websites: updatedList });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2">
          Allowed Websites List
          <Tooltip title="When enabled, Magentic-UI will only be able to visit websites you add to the list below.">
            <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
          </Tooltip>
        </span>
        {cachedWebsites.length === 0 && (
          <Switch
            checked={allowedlistEnabled}
            checkedChildren="Restricted to List"
            unCheckedChildren="All Websites Allowed"
            onChange={(checked) => {
              setAllowedlistEnabled(checked);
              if (!checked) {
                setCachedWebsites([]);
                handleUpdateConfig({ allowed_websites: undefined });
              }
            }}
          />
        )}
      </div>
      <Space direction="vertical" style={{ width: "100%" }}>
        {allowedlistEnabled || cachedWebsites.length > 0 ? (
          <>
            <div className="flex w-full gap-2">
              <Input
                placeholder="https://example.com"
                value={websiteInput}
                onChange={(e) => setWebsiteInput(e.target.value)}
                onPressEnter={addWebsite}
                className="flex-1"
              />
              <Button icon={<Plus size={16} />} onClick={addWebsite}>
                Add
              </Button>
            </div>
            <div>
              {cachedWebsites.length === 0 ? (
                <div></div>
              ) : (
                cachedWebsites.map((site, index) => (
                  <Tag
                    key={index}
                    closable
                    onClose={() => removeWebsite(site)}
                    style={{ margin: "0 8px 8px 0" }}
                  >
                    {site}
                  </Tag>
                ))
              )}
            </div>
          </>
        ) : (
          <div className="text-secondary italic"></div>
        )}
      </Space>
    </div>
  );
};

export default AllowedWebsitesList;
