import React from "react";
import { Flex, Switch, Tooltip, Input, Button, List, Tag } from "antd";
import { InfoCircleOutlined, PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";

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

  const { t } = useTranslation();

  return (
    <Flex vertical gap="small">
      <Flex align="center" justify="space-between" wrap gap="small">
        <Flex align="center" justify="start" gap="small">
          {t('generalSettings.allowedWebsites')}
          <Tooltip title={t('generalSettings.allowedWebsitesTooltip')}>
            <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
          </Tooltip>
        </Flex>
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
            style={{flex: "none"}}
          />
        )}
      </Flex>
      <Flex vertical gap="large">
        {(allowedlistEnabled || cachedWebsites.length > 0) &&
          <Flex vertical gap="small">
            <Flex gap="large">
              <Input
                placeholder="https://example.com"
                value={websiteInput}
                onChange={(e) => setWebsiteInput(e.target.value)}
                onPressEnter={addWebsite}
                // className="flex-1"
              />
              <Button icon={<PlusOutlined size={16} />} onClick={addWebsite}>
                Add
              </Button>
            </Flex>
            <Flex wrap="wrap" gap="large">
              {(cachedWebsites.length > 0) && 
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
              }
            </Flex>
          </Flex>
        }
      </Flex>
    </Flex>
  );
};

export default AllowedWebsitesList;
