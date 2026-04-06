export function formatKw(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "--";
  }

  return `${Number(value).toFixed(2)} kW`;
}

export function formatNumber(value: string | number | null | undefined, digits = 1) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return "--";
  }

  return numericValue.toFixed(digits);
}

export function formatUpdateTimestamp(updated?: string) {
  if (!updated) {
    return "Last updated: --";
  }

  const parts = updated.split(",");

  if (parts.length >= 6) {
    const [year, month, day, hour, minute, second] = parts.map((part) => Number(part));
    const timestamp = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
    return `Last updated: ${timestamp.toLocaleString()}`;
  }

  return "Last updated: --";
}

export function formatTimestampFromUnix(timestamp?: number | null) {
  if (!timestamp || !Number.isFinite(timestamp)) {
    return "--";
  }

  return new Date(timestamp * 1000).toLocaleString();
}

export function formatRelativeAgeFromUnix(timestamp?: number | null) {
  if (!timestamp || !Number.isFinite(timestamp)) {
    return "--";
  }

  const diffSeconds = Math.max(0, Math.round(Date.now() / 1000 - timestamp));

  if (diffSeconds < 60) {
    return `${diffSeconds}s ago`;
  }

  if (diffSeconds < 3600) {
    return `${Math.round(diffSeconds / 60)}m ago`;
  }

  if (diffSeconds < 86_400) {
    return `${Math.round(diffSeconds / 3600)}h ago`;
  }

  return `${Math.round(diffSeconds / 86_400)}d ago`;
}
