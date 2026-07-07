import { useCallback } from "react";
import { api, getApiError } from "../api/client";
import { HtmlTemplate } from "../components/HtmlTemplate";
import portfolioHtml from "../templates/portfolio.html?raw";
import type { PortfolioItem, PortfolioSummary } from "../types";
import { currency, signedCurrency } from "../utils/format";

function setText(root: HTMLElement, selector: string, value: string) {
  const element = root.querySelector<HTMLElement>(selector);
  if (element) {
    element.textContent = value;
  }
}

export function PortfolioPage() {
  const onMount = useCallback((root: HTMLDivElement) => {
    const form = root.querySelector<HTMLFormElement>("[data-portfolio-form]");
    const errorBox = root.querySelector<HTMLElement>("[data-error]");
    const tableBody = root.querySelector<HTMLElement>("[data-holdings-body]");
    const submitButton = root.querySelector<HTMLButtonElement>("[data-submit]");

    const showError = (message: string) => {
      if (!errorBox) {
        return;
      }
      errorBox.textContent = message;
      errorBox.classList.toggle("hidden", !message);
    };

    const renderRows = (items: PortfolioItem[]) => {
      if (!tableBody) {
        return;
      }
      if (items.length === 0) {
        tableBody.innerHTML = '<tr><td class="px-4 py-8 text-center font-semibold text-slate-500" colspan="8">No holdings yet.</td></tr>';
        return;
      }
      tableBody.innerHTML = items
        .map((item) => {
          const gain = Number(item.unrealized_gain_loss ?? 0);
          return `
            <tr class="bg-white">
              <td class="px-4 py-3 font-bold text-slate-950">${item.set_number}</td>
              <td class="px-4 py-3 text-slate-700">${item.set_name ?? "--"}</td>
              <td class="px-4 py-3 capitalize text-slate-700">${item.condition}</td>
              <td class="px-4 py-3 text-slate-700">${item.quantity}</td>
              <td class="px-4 py-3 text-slate-700">${currency(item.purchase_price)}</td>
              <td class="px-4 py-3 text-slate-700">${currency(item.current_total_value)}</td>
              <td class="px-4 py-3 font-bold ${gain >= 0 ? "text-emerald-700" : "text-red-700"}">${signedCurrency(item.unrealized_gain_loss)}</td>
              <td class="px-4 py-3"><button data-delete-id="${item.id}" class="secondary-button" type="button">Delete</button></td>
            </tr>
          `;
        })
        .join("");
    };

    const loadPortfolio = async () => {
      showError("");
      try {
        const [itemsResponse, summaryResponse] = await Promise.all([
          api.get<PortfolioItem[]>("/portfolio"),
          api.get<PortfolioSummary>("/portfolio/summary")
        ]);
        renderRows(itemsResponse.data);
        setText(root, "[data-total-value]", currency(summaryResponse.data.estimated_current_value));
        setText(root, "[data-total-cost]", currency(summaryResponse.data.total_cost_basis));
        setText(root, "[data-gain-loss]", signedCurrency(summaryResponse.data.unrealized_gain_loss));
        setText(root, "[data-total-sets]", String(summaryResponse.data.total_quantity));
      } catch (error) {
        renderRows([]);
        showError(getApiError(error));
      }
    };

    const handleSubmit = async (event: SubmitEvent) => {
      event.preventDefault();
      if (!form) {
        return;
      }
      const values = new FormData(form);
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = "Adding...";
      }
      try {
        const acquiredAt = String(values.get("acquired_at") ?? "");
        await api.post("/portfolio/items", {
          set_number: String(values.get("set_number") ?? ""),
          quantity: Number(values.get("quantity") ?? 1),
          purchase_price: Number(values.get("purchase_price") ?? 0),
          condition: String(values.get("condition") ?? "unknown"),
          acquired_at: acquiredAt ? new Date(acquiredAt).toISOString() : null,
          notes: String(values.get("notes") ?? "") || null
        });
        form.reset();
        await loadPortfolio();
      } catch (error) {
        showError(getApiError(error));
      } finally {
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = "Add item";
        }
      }
    };

    const handleDelete = async (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      const button = target?.closest<HTMLButtonElement>("[data-delete-id]");
      if (!button) {
        return;
      }
      try {
        await api.delete(`/portfolio/items/${button.dataset.deleteId}`);
        await loadPortfolio();
      } catch (error) {
        showError(getApiError(error));
      }
    };

    form?.addEventListener("submit", handleSubmit);
    tableBody?.addEventListener("click", handleDelete);
    void loadPortfolio();

    return () => {
      form?.removeEventListener("submit", handleSubmit);
      tableBody?.removeEventListener("click", handleDelete);
    };
  }, []);

  return <HtmlTemplate html={portfolioHtml} onMount={onMount} />;
}
