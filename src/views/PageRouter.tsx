import { SidebarNavigation, useParams } from "@decky/ui";
import type { FC } from "react";
import { FaWrench } from "react-icons/fa6";

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
      ]}
    />
  );
};

export default PageRouter;
