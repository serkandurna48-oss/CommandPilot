export function revealProjectDetail(
  detail: Pick<HTMLElement, "scrollIntoView"> | null,
  isStacked: boolean,
): void {
  if (isStacked) detail?.scrollIntoView({ block: "start", behavior: "smooth" });
}
