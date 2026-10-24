import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/section";
import { StatusBadge } from "@/components/status-badge";
import { api, unwrap } from "@/lib/api/client";
import { formatDuration, formatKst } from "@/lib/format";

const PAGE_SIZE = 50;

export default function RunsPage({ searchParams }: PageProps<"/runs">) {
  return (
    <>
      <h1 className="mb-6 text-2xl font-bold">실행 이력</h1>
      {/* searchParams는 요청 시점 값이라 Suspense 안에서 읽는다 */}
      <Suspense fallback={<Loading />}>
        <RunsTable searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function RunsTable({ searchParams }: { searchParams: PageProps<"/runs">["searchParams"] }) {
  const page = Math.max(1, Number((await searchParams).page ?? 1) || 1);
  const runs = unwrap(
    await api.GET("/runs", { params: { query: { limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE } } }),
  );

  return (
    <>
      <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-left text-xs text-zinc-500">
            <tr>
              <th className="px-4 py-2">번호</th>
              <th className="px-4 py-2">시작</th>
              <th className="px-4 py-2">상태</th>
              <th className="px-4 py-2">실행 방식</th>
              <th className="px-4 py-2">성공</th>
              <th className="px-4 py-2">걸린 시간</th>
              <th className="px-4 py-2">메시지</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50">
                <td className="px-4 py-2">
                  <Link href={`/runs/${run.id}`} className="text-sky-700 hover:underline">
                    #{run.id}
                  </Link>
                </td>
                <td className="px-4 py-2 whitespace-nowrap">{formatKst(run.started_at)}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={run.status} />
                </td>
                <td className="px-4 py-2">{run.trigger === "schedule" ? "예약" : "수동"}</td>
                <td className="px-4 py-2">
                  {run.products_succeeded}/{run.products_total}
                </td>
                <td className="px-4 py-2 whitespace-nowrap">{formatDuration(run.started_at, run.finished_at)}</td>
                <td className="px-4 py-2 text-zinc-500">{run.error_message ?? ""}</td>
              </tr>
            ))}
            {runs.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-zinc-500">
                  실행 기록이 없다
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <nav className="mt-4 flex gap-4 text-sm">
        {page > 1 && <Link href={`/runs?page=${page - 1}`}>← 최근</Link>}
        {runs.length === PAGE_SIZE && <Link href={`/runs?page=${page + 1}`}>이전 →</Link>}
      </nav>
    </>
  );
}
