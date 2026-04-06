type StructuredValue = unknown;
type StructuredObject = Record<string, unknown>;

interface AlertStructuredEvidenceProps {
  title: string;
  data: StructuredObject;
  nested?: boolean;
  testId?: string;
}

function isRecord(value: unknown): value is StructuredObject {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function toTitleCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatLabel(key: string) {
  return key
    .split("_")
    .map((part) => {
      if (["kw", "pct", "ts", "ip", "id"].includes(part)) {
        return part.toUpperCase();
      }

      return toTitleCase(part);
    })
    .join(" ");
}

function formatTs(ts: number) {
  return new Date(ts * 1000).toLocaleString();
}

function formatDuration(totalSeconds: number) {
  const rounded = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const seconds = rounded % 60;
  const parts = [
    hours > 0 ? `${hours}h` : null,
    minutes > 0 ? `${minutes}m` : null,
    seconds > 0 || (hours === 0 && minutes === 0) ? `${seconds}s` : null
  ].filter(Boolean);

  return parts.join(" ");
}

function formatScalar(key: string, value: string | number | boolean) {
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (typeof value === "number") {
    if (key.endsWith("_ts")) {
      return formatTs(value);
    }

    if (key.endsWith("_seconds")) {
      return formatDuration(value);
    }

    if (key.endsWith("_kw")) {
      return `${value.toFixed(2)} kW`;
    }

    if (key.endsWith("_pct") || key.includes("percent")) {
      const sign = value > 0 ? "+" : "";
      return `${sign}${value.toFixed(1)}%`;
    }

    if (key.includes("score") || key.includes("stddev")) {
      return value.toFixed(2);
    }

    if (key.includes("count") || key.endsWith("_threshold")) {
      return String(Math.round(value));
    }

    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }

  return value;
}

function renderPrimitiveArray(title: string, values: StructuredValue[]) {
  const primitives = values.filter((value) => value !== null && value !== undefined && !Array.isArray(value) && !isRecord(value));

  if (primitives.length === 0) {
    return null;
  }

  return (
    <div className="alert-structured-array-block">
      <p className="k-title alert-structured-title">{title}</p>
      <div className="alert-structured-pill-row">
        {primitives.map((value, index) => (
          <span key={`${title}-${index}`} className="pill alert-structured-pill">
            {typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}
          </span>
        ))}
      </div>
    </div>
  );
}

function renderArray(title: string, values: StructuredValue[]) {
  const primitiveBlock = renderPrimitiveArray(title, values);

  if (primitiveBlock) {
    return primitiveBlock;
  }

  const objects = values.filter((value): value is StructuredObject => isRecord(value));

  if (objects.length === 0) {
    return null;
  }

  return (
    <div className="alert-structured-array-block">
      <p className="k-title alert-structured-title">{title}</p>
      <div className="alert-structured-array-grid">
        {objects.map((item, index) => (
          <AlertStructuredEvidence key={`${title}-${index}`} title={`Entry ${index + 1}`} data={item} nested />
        ))}
      </div>
    </div>
  );
}

export function AlertStructuredEvidence({ title, data, nested = false, testId }: AlertStructuredEvidenceProps) {
  const entries = Object.entries(data).filter(([, value]) => {
    if (value === null || value === undefined) {
      return false;
    }

    if (Array.isArray(value)) {
      return value.length > 0;
    }

    if (isRecord(value)) {
      return Object.keys(value).length > 0;
    }

    return true;
  });

  if (entries.length === 0) {
    return null;
  }

  return (
    <section
      className={`alert-structured-section ${nested ? "alert-structured-section-nested" : ""}`.trim()}
      data-testid={testId}
    >
      <p className="k-title alert-structured-title">{title}</p>
      <div className="alert-structured-content">
        {entries.map(([key, value]) => {
          if (Array.isArray(value)) {
            return <div key={key}>{renderArray(formatLabel(key), value as StructuredValue[])}</div>;
          }

          if (isRecord(value)) {
            return <AlertStructuredEvidence key={key} title={formatLabel(key)} data={value} nested />;
          }

          return (
            <div key={key} className="alert-evidence-item">
              <p className="muted alert-structured-label">{formatLabel(key)}</p>
              <p className="alert-structured-value">{formatScalar(key, value as string | number | boolean)}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
