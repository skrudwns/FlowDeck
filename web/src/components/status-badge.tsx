// 실행 상태(success/partial/failed/running)와 상품별 상태(ok/http_error/...)를 같이 쓴다
const STYLES: Record<string, { label: string; className: string }> = {
  success: { label: "성공", className: "bg-emerald-100 text-emerald-800" },
  ok: { label: "정상", className: "bg-emerald-100 text-emerald-800" },
  partial: { label: "일부 실패", className: "bg-amber-100 text-amber-800" },
  running: { label: "실행 중", className: "bg-sky-100 text-sky-800" },
  failed: { label: "실패", className: "bg-red-100 text-red-800" },
  http_error: { label: "요청 실패", className: "bg-red-100 text-red-800" },
  parse_failed: { label: "파싱 실패", className: "bg-red-100 text-red-800" },
  blocked: { label: "차단", className: "bg-red-200 text-red-900" },
  disallowed: { label: "robots 금지", className: "bg-zinc-200 text-zinc-800" },
};

export function StatusBadge({ status }: { status: string }) {
  const style = STYLES[status] ?? { label: status, className: "bg-zinc-100 text-zinc-700" };
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${style.className}`}>
      {style.label}
    </span>
  );
}
