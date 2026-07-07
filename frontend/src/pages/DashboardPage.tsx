import { HtmlTemplate } from "../components/HtmlTemplate";
import dashboardHtml from "../templates/dashboard.html?raw";

export function DashboardPage() {
  return <HtmlTemplate html={dashboardHtml} />;
}
