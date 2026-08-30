import { SidebarNavigation, useParams } from "@decky/ui";
import type { FC } from "react";
import { FaStethoscope, FaWrench } from "react-icons/fa6";

import DiagnosticsPage from "./DiagnosticsPage";
import RelayPage from "./RelayPage";

const PageRouter: FC = () => {
  const { appid: rawAppid } = useParams<{ appid: string }>();
  const appid = Number.parseInt(rawAppid ?? "", 10);
  return (
    <SidebarNavigation
      title="Trainer Relay"
      showTitle={true}
      pages={[
        {
          title: "Trainer Relay",
          content: <RelayPage appid={appid} />,
          icon: <FaWrench />,
          hideTitle: false,
        },
        {
          title: "Diagnostics",
          content: <DiagnosticsPage />,
          icon: <FaStethoscope />,
          hideTitle: false,
        },
      ]}
    />
  );
};

export default PageRouter;
