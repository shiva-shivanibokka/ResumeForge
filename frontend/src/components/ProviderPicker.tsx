import { useStore } from "../store";
import { Badge, Input, Label, Select } from "./ui";

// Choose an LLM provider + model and supply a key. Free providers are flagged so
// a visitor can run the live demo at no cost with their own free key.
export function ProviderPicker() {
  const { providers, provider, model, apiKey, onProviderChange, set } = useStore();
  const current = providers.find((p) => p.key === provider);

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div>
        <Label htmlFor="provider">Engine</Label>
        <Select id="provider" value={provider} onChange={(e) => onProviderChange(e.target.value)}>
          {providers.length === 0 && <option value={provider}>{provider}</option>}
          {providers.map((p) => (
            <option key={p.key} value={p.key}>
              {p.label} — {p.free_tier ? "free" : "paid"}
            </option>
          ))}
        </Select>
      </div>

      <div>
        <Label htmlFor="model">Model</Label>
        <Select id="model" value={model} onChange={(e) => set("model", e.target.value)}>
          {(current?.models ?? [{ id: model, label: model, free: false }]).map((m) => (
            <option key={m.id} value={m.id}>
              {m.label} — {m.free ? "free" : "paid"}
            </option>
          ))}
        </Select>
      </div>

      <div>
        <Label htmlFor="apiKey">API key</Label>
        <Input
          id="apiKey"
          type="password"
          autoComplete="off"
          placeholder={current ? `${current.env_key_name} or paste here` : "Your API key"}
          value={apiKey}
          onChange={(e) => set("apiKey", e.target.value)}
        />
      </div>

      {current && (
        <div className="sm:col-span-3 flex items-center gap-2 text-xs text-ash">
          {current.free_tier ? <Badge tone="free">free tier</Badge> : <Badge tone="ember">paid</Badge>}
          <span>{current.notes}</span>
        </div>
      )}
    </div>
  );
}
