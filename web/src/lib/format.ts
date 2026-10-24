// API는 UTC로 주고, 화면은 한국 시간으로 보여준다 (ADR-0008, ADR-0009)
const kst = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const kstShort = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function formatKst(iso: string | null | undefined): string {
  return iso ? kst.format(new Date(iso)) : "-";
}

export function formatKstShort(iso: string): string {
  return kstShort.format(new Date(iso));
}

const SOURCE_LABELS: Record<string, string> = { danawa: "다나와", mockshop: "연습 쇼핑몰" };

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

const won = new Intl.NumberFormat("ko-KR");

export function formatWon(value: number | null | undefined): string {
  return value == null ? "-" : `${won.format(value)}원`;
}

export function formatDuration(startIso: string, endIso: string | null): string {
  if (!endIso) return "진행 중";
  const seconds = Math.round((new Date(endIso).getTime() - new Date(startIso).getTime()) / 1000);
  return seconds >= 60 ? `${Math.floor(seconds / 60)}분 ${seconds % 60}초` : `${seconds}초`;
}
