import { Suspense } from "react";

import { Loading } from "@/components/section";
import { api, unwrap } from "@/lib/api/client";
import { formatKst } from "@/lib/format";

// 대상 목록 파일의 git 이력을 대신하는 기록 (ADR-0011)
const ACTIONS: Record<string, string> = {
  product_added: "수집 대상 추가",
  product_reactivated: "수집 대상 재개",
  product_deactivated: "수집 대상 중지",
  schedule_changed: "주기 변경",
  run_requested: "수동 실행 요청",
};

const ACTORS: Record<string, string> = { portal: "포털", cli: "CLI" };

export default function ActivityPage() {
  return (
    <>
      <h1 className="mb-6 text-2xl font-bold">변경 이력</h1>
      <Suspense fallback={<Loading />}>
        <ActivityTable />
      </Suspense>
    </>
  );
}

async function ActivityTable() {
  const entries = unwrap(await api.GET("/audit-log", { params: { query: { limit: 200 } } }));
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white">
      <table className="w-full text-sm">
        <thead className="border-b border-zinc-200 bg-zinc-50 text-left text-xs text-zinc-500">
          <tr>
            <th className="px-4 py-2">시각</th>
            <th className="px-4 py-2">변경</th>
            <th className="px-4 py-2">대상</th>
            <th className="px-4 py-2">내용</th>
            <th className="px-4 py-2">경로</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id} className="border-b border-zinc-100 last:border-0">
              <td className="px-4 py-2 whitespace-nowrap">{formatKst(e.at)}</td>
              <td className="px-4 py-2 whitespace-nowrap">{ACTIONS[e.action] ?? e.action}</td>
              <td className="px-4 py-2">{e.target}</td>
              <td className="px-4 py-2 text-zinc-600">{e.detail ?? ""}</td>
              <td className="px-4 py-2">{ACTORS[e.actor] ?? e.actor}</td>
            </tr>
          ))}
          {entries.length === 0 && (
            <tr>
              <td colSpan={5} className="px-4 py-6 text-center text-zinc-500">
                변경 기록이 없다
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
