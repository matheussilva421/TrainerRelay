import { useParams } from "@decky/ui";
import type { FC } from "react";

import RelayPage from "./RelayPage";

const PageRouter: FC = () => {
  const { appid: rawAppid } = useParams<{ appid: string }>();
  const appid = Number.parseInt(rawAppid ?? "", 10);
  return <RelayPage appid={appid} />;
};

export default PageRouter;
