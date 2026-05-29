const JERSEY_COLOR_ALIASES = new Map<string, string>([
  ["black", "black"],
  ["dark", "black"],
  ["navy", "blue"],
  ["blue", "blue"],
  ["teal", "blue"],
  ["red", "red"],
  ["maroon", "red"],
  ["white", "white"],
  ["light", "white"],
  ["yellow", "yellow"],
  ["gold", "yellow"],
  ["green", "green"],
  ["orange", "orange"],
  ["purple", "purple"],
  ["gray", "gray"],
  ["grey", "gray"],
  ["pink", "pink"]
]);

interface TeamIdentityInput {
  selectedTeamId?: string | null;
  selectedColorLabel?: string | null;
  selectedLabel?: string | null;
  candidateTeamId?: string | null;
  candidateColorLabel?: string | null;
  candidateLabel?: string | null;
}

export function cleanTeamText(value: unknown, maxLength = 80): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const cleaned = value.trim().split(/\s+/).join(" ");
  return cleaned.length > 0 ? cleaned.slice(0, maxLength) : null;
}

export function teamKey(value: string | null | undefined): string | null {
  return cleanTeamText(value)?.toLowerCase() ?? null;
}

export function resolveJerseyColor(...values: unknown[]): string | null {
  for (const value of values) {
    const cleaned = cleanTeamText(value, 120);
    if (!cleaned) {
      continue;
    }

    const words = cleaned.toLowerCase().match(/[a-z]+/g) ?? [];
    for (const word of words) {
      const color = JERSEY_COLOR_ALIASES.get(word);
      if (color) {
        return color;
      }
    }
  }
  return null;
}

export function teamIdentityMatches(input: TeamIdentityInput): boolean {
  if (teamIdColorConflictsWithExplicitColor(input.selectedTeamId, input.selectedColorLabel, input.selectedLabel)) {
    return false;
  }
  if (teamIdColorConflictsWithExplicitColor(input.candidateTeamId, input.candidateColorLabel, input.candidateLabel)) {
    return false;
  }

  const selectedTeamKey = teamKey(input.selectedTeamId);
  const candidateTeamKey = teamKey(input.candidateTeamId);
  if (selectedTeamKey && candidateTeamKey && selectedTeamKey === candidateTeamKey) {
    return true;
  }

  const selectedColor = resolveJerseyColor(input.selectedColorLabel, input.selectedLabel, input.selectedTeamId);
  const candidateColor = resolveJerseyColor(input.candidateColorLabel, input.candidateLabel, input.candidateTeamId);
  return Boolean(selectedColor && candidateColor && selectedColor === candidateColor);
}

function teamIdColorConflictsWithExplicitColor(
  teamId: string | null | undefined,
  colorLabel: string | null | undefined,
  label: string | null | undefined
): boolean {
  const teamIdColor = resolveJerseyColor(teamId);
  const explicitColor = resolveJerseyColor(colorLabel, label);
  return Boolean(teamIdColor && explicitColor && teamIdColor !== explicitColor);
}
