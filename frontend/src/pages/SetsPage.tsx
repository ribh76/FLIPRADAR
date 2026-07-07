import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { HtmlTemplate } from "../components/HtmlTemplate";
import setsHtml from "../templates/sets.html?raw";

export function SetsPage() {
  const navigate = useNavigate();

  const onMount = useCallback(
    (root: HTMLDivElement) => {
      const form = root.querySelector<HTMLFormElement>("[data-set-search-form]");
      const message = root.querySelector<HTMLElement>("[data-message]");

      const handleSubmit = (event: SubmitEvent) => {
        event.preventDefault();
        const values = new FormData(form ?? undefined);
        const setNumber = String(values.get("set_number") ?? "").trim();
        if (!setNumber) {
          if (message) {
            message.textContent = "Enter a LEGO set number.";
            message.classList.remove("hidden");
          }
          return;
        }
        navigate(`/sets/${encodeURIComponent(setNumber)}`);
      };

      form?.addEventListener("submit", handleSubmit);
      return () => form?.removeEventListener("submit", handleSubmit);
    },
    [navigate]
  );

  return <HtmlTemplate html={setsHtml} onMount={onMount} />;
}
