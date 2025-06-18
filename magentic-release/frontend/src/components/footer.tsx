import * as React from "react";
import { useConfigStore } from "../hooks/store";
import { fetchVersion } from "./utils";


const Footer = () => {
  const version = useConfigStore((state) => state.version);
  const setVersion = useConfigStore((state) => state.setVersion);

  React.useEffect(() => {
    if (version === null) {
      fetchVersion().then((data) => {
        if (data && data.data) {
          setVersion(data.data.version);
        }
      });
    }
  }, []);
  return (
    <div className="text-primary p-1  flex h-1">

    </div>
  );
};
export default Footer;
