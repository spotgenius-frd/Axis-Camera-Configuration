"use client";

export const US_TIME_ZONES = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
] as const;

export function getSupportedUsTimeZones(
  supportedTimeZones?: string[] | null,
): string[] {
  if (!supportedTimeZones || supportedTimeZones.length === 0) {
    return [...US_TIME_ZONES];
  }
  return US_TIME_ZONES.filter((timeZone) => supportedTimeZones.includes(timeZone));
}
