import { useCallback } from "react";
import { api, getApiError } from "../api/client";
import { HtmlTemplate } from "../components/HtmlTemplate";
import analyzeHtml from "../templates/analyze.html?raw";
import type { AnalyzeResponse } from "../types";
import { currency, numberValue } from "../utils/format";

function setText(root: HTMLElement, selector: string, value: string) {
  const element = root.querySelector<HTMLElement>(selector);
  if (element) {
    element.textContent = value;
  }
}

function verdictClasses(verdict: string) {
  if (verdict === "BUY" || verdict === "SELL") {
    return "border-emerald-200 bg-emerald-100 text-emerald-800";
  }
  if (verdict === "PASS") {
    return "border-red-200 bg-red-100 text-red-800";
  }
  if (verdict === "WATCH") {
    return "border-amber-200 bg-amber-100 text-amber-900";
  }
  return "border-blue-200 bg-blue-100 text-blue-800";
}

export function AnalyzePage() {
  const onMount = useCallback((root: HTMLDivElement) => {
    const form = root.querySelector<HTMLFormElement>("[data-analyze-form]");
    const errorBox = root.querySelector<HTMLElement>("[data-error]");
    const submitButton = root.querySelector<HTMLButtonElement>("[data-submit]");
    const condition = root.querySelector<HTMLSelectElement>(
      "select[name='condition']",
    );

    const showError = (message: string) => {
      if (!errorBox) {
        return;
      }
      errorBox.textContent = message;
      errorBox.classList.toggle("hidden", !message);
    };

    const renderResult = (result: AnalyzeResponse) => {
      const verdict = result.recommendation;
      const verdictClass = verdictClasses(verdict);
      const badge = root.querySelector<HTMLElement>("[data-verdict-badge]");
      const card = root.querySelector<HTMLElement>("[data-verdict-card]");

      setText(root, "[data-result-set]", result.set_number);
      setText(root, "[data-verdict]", verdict);
      setText(root, "[data-fair-value]", currency(result.fair_value));
      setText(root, "[data-asking-price]", currency(result.asking_price));
      setText(root, "[data-score]", `${result.score}/100`);
      setText(root, "[data-confidence]", result.confidence.toUpperCase());
      setText(root, "[data-market-low]", currency(result.market_low));
      setText(root, "[data-market-high]", currency(result.market_high));
      setText(root, "[data-listing-count]", numberValue(result.listing_count));
      setText(
        root,
        "[data-condition]",
        condition?.value.toUpperCase() ?? "UNKNOWN",
      );
      setText(root, "[data-reasoning]", result.reasoning);

      if (badge) {
        badge.textContent = verdict;
        badge.className = `inline-flex items-center rounded-md border px-2 py-1 text-xs font-bold ${verdictClass}`;
      }
      if (card) {
        card.className = `rounded-lg border p-8 text-center ${verdictClass}`;
      }
    };

    const handleSubmit = async (event: SubmitEvent) => {
      event.preventDefault();
      if (!form) {
        return;
      }
      const values = new FormData(form);
      const askingPrice = String(values.get("asking_price") ?? "");

      showError("");
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = "Analyzing...";
      }

      try {
        const response = await api.post<AnalyzeResponse>("/analyze", {
          set_number: String(values.get("set_number") ?? ""),
          user_goal: String(values.get("user_goal") ?? "buy_vs_pass"),
          condition: String(values.get("condition") ?? "unknown"),
          asking_price: askingPrice ? Number(askingPrice) : null,
        });
        renderResult(response.data);
      } catch (error) {
        showError(getApiError(error));
      } finally {
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = "Analyze";
        }
      }
    };

    const handleConditionChange = () => {
      setText(
        root,
        "[data-condition]",
        condition?.value.toUpperCase() ?? "UNKNOWN",
      );
    };

    form?.addEventListener("submit", handleSubmit);
    condition?.addEventListener("change", handleConditionChange);
    return () => {
      form?.removeEventListener("submit", handleSubmit);
      condition?.removeEventListener("change", handleConditionChange);
    };
  }, []);

  return <HtmlTemplate html={analyzeHtml} onMount={onMount} />;
}
