import type { FormEvent } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

export function SetsPage() {
  const navigate = useNavigate();
  const [setNumber, setSetNumber] = useState("");
  const [message, setMessage] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedSetNumber = setNumber.trim();
    if (!trimmedSetNumber) {
      setMessage("Enter a LEGO set number.");
      return;
    }
    navigate(`/sets/${encodeURIComponent(trimmedSetNumber)}`);
  }

  return (
    <section>
      <div className="mb-7">
        <h1 className="text-3xl font-bold text-white">Set Detail Lookup</h1>
        <p className="mt-2 text-blue-100">
          Search a LEGO set number to view metadata, valuation, and market
          status.
        </p>
      </div>

      <section className="page-card">
        <form
          className="flex flex-col gap-3 sm:flex-row"
          onSubmit={handleSubmit}
        >
          <label className="flex-1">
            <span className="sr-only">Set number</span>
            <input
              className="field-input"
              onChange={(event) => setSetNumber(event.target.value)}
              placeholder="Enter set number, for example 75192-1"
              value={setNumber}
            />
          </label>
          <button className="primary-button" type="submit">
            Search
          </button>
        </form>
        {message ? (
          <p className="mt-4 text-sm font-semibold text-red-700">{message}</p>
        ) : null}
      </section>
    </section>
  );
}
