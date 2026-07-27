import type { FormEvent } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, FormAlert, TextField } from "../../components/ui";

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
      <Card>
        <form
          className="flex flex-col gap-3 sm:flex-row"
          onSubmit={handleSubmit}
        >
          <div className="flex-1">
            <TextField
              label="Set number"
              onChange={(event) => setSetNumber(event.target.value)}
              placeholder="Enter set number, for example 75192-1"
              value={setNumber}
            />
          </div>
          <button className="primary-button self-end" type="submit">
            Search
          </button>
        </form>
        <div className="mt-4">
          <FormAlert>{message}</FormAlert>
        </div>
      </Card>
    </section>
  );
}
