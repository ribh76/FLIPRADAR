import { useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getApiError } from "../api/client";
import { HtmlTemplate } from "../components/HtmlTemplate";
import setDetailHtml from "../templates/set-detail.html?raw";
import type { SetDetail } from "../types";
import { currency, numberValue } from "../utils/format";

function setText(root: HTMLElement, selector: string, value: string) {
  const element = root.querySelector<HTMLElement>(selector);
  if (element) {
    element.textContent = value;
  }
}

export function SetDetailPage() {
  const { setNumber } = useParams();
  const navigate = useNavigate();

  const onMount = useCallback(
    (root: HTMLDivElement) => {
      const form = root.querySelector<HTMLFormElement>("[data-set-search-form]");
      const input = root.querySelector<HTMLInputElement>("input[name='set_number']");
      const errorBox = root.querySelector<HTMLElement>("[data-error]");
      const loading = root.querySelector<HTMLElement>("[data-loading]");
      const detailShell = root.querySelector<HTMLElement>("[data-detail]");
      const refreshButton = root.querySelector<HTMLElement>("[data-refresh]");

      const showError = (message: string) => {
        if (!errorBox) {
          return;
        }
        errorBox.textContent = message;
        errorBox.classList.toggle("hidden", !message);
      };

      const setLoading = (isLoading: boolean) => {
        loading?.classList.toggle("hidden", !isLoading);
        loading?.classList.toggle("flex", isLoading);
      };

      const renderDetail = (detail: SetDetail) => {
        const hasMarketData = detail.valuation_status === "available";
        const status = root.querySelector<HTMLElement>("[data-valuation-status]");
        const noMarket = root.querySelector<HTMLElement>("[data-no-market]");

        detailShell?.classList.remove("hidden");
        if (input) {
          input.value = detail.set_number;
        }

        setText(root, "[data-name]", detail.name);
        setText(root, "[data-set-number]", detail.set_number);
        setText(root, "[data-theme]", detail.theme ?? "--");
        setText(root, "[data-subtheme]", detail.subtheme ?? "--");
        setText(root, "[data-release-year]", detail.release_year?.toString() ?? "--");
        setText(root, "[data-retirement-year]", detail.retirement_year?.toString() ?? "--");
        setText(root, "[data-piece-count]", numberValue(detail.piece_count));
        setText(root, "[data-minifig-count]", numberValue(detail.minifig_count));
        setText(root, "[data-fair-value]", currency(detail.fair_value));
        setText(root, "[data-market-low]", currency(detail.market_low));
        setText(root, "[data-market-high]", currency(detail.market_high));
        setText(root, "[data-listing-count]", numberValue(detail.listing_count));
        setText(root, "[data-confidence]", detail.confidence?.toUpperCase() ?? "--");

        if (status) {
          status.textContent = detail.valuation_status;
          status.className = `mt-3 inline-flex rounded-md border px-3 py-2 text-sm font-bold ${
            hasMarketData
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-amber-200 bg-amber-50 text-amber-900"
          }`;
        }

        noMarket?.classList.toggle("hidden", hasMarketData);
        refreshButton?.classList.toggle("hidden", !import.meta.env.DEV);
      };

      const loadDetail = async (number: string) => {
        showError("");
        setLoading(true);
        detailShell?.classList.add("hidden");
        try {
          const response = await api.get<SetDetail>(`/sets/${encodeURIComponent(number)}`);
          renderDetail(response.data);
        } catch (error) {
          showError(getApiError(error));
        } finally {
          setLoading(false);
        }
      };

      const handleSubmit = (event: SubmitEvent) => {
        event.preventDefault();
        const values = new FormData(form ?? undefined);
        const nextSetNumber = String(values.get("set_number") ?? "").trim();
        if (nextSetNumber) {
          navigate(`/sets/${encodeURIComponent(nextSetNumber)}`);
        }
      };

      form?.addEventListener("submit", handleSubmit);
      if (setNumber) {
        if (input) {
          input.value = setNumber;
        }
        void loadDetail(setNumber);
      }

      return () => form?.removeEventListener("submit", handleSubmit);
    },
    [navigate, setNumber]
  );

  return <HtmlTemplate html={setDetailHtml} onMount={onMount} />;
}
