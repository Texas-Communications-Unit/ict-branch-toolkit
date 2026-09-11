const METERS_TO_FEET = 3.280839895013123;
const METERS_PER_MILE = 1609.344;
const KILOMETERS_PER_MILE = 1.609344;

export type MetricValue = number | string | null | undefined;

function parseMetricValue(value: MetricValue): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatMetricSource(value: number) {
  return Number.isInteger(value)
    ? value.toString()
    : value.toFixed(3).replace(/\.?0+$/, "");
}

export function formatMetersAsFeet(value: MetricValue): string {
  const meters = parseMetricValue(value);
  if (meters === null) return "Not listed";
  const rawFeet = meters * METERS_TO_FEET;
  const feet = Math.round(
    rawFeet + Number.EPSILON * Math.max(1, Math.abs(rawFeet)),
  );
  return `${feet.toLocaleString("en-US")} ft (${formatMetricSource(meters)} m)`;
}

export function formatMetersAsMiles(value: MetricValue): string {
  const meters = parseMetricValue(value);
  if (meters === null) return "Not listed";
  const miles = meters / METERS_PER_MILE;
  return `${miles.toFixed(2)} mi (${formatMetricSource(meters)} m)`;
}

export function formatKilometersAsMiles(value: MetricValue): string {
  const kilometers = parseMetricValue(value);
  if (kilometers === null) return "Not listed";
  const miles = kilometers / KILOMETERS_PER_MILE;
  return `${miles.toFixed(2)} mi (${formatMetricSource(kilometers)} km)`;
}
