import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { Loading, Section } from "@/components/section";
import { StatusBadge } from "@/components/status-badge";
import { api, unwrap } from "@/lib/api/client";
import { formatDuration, formatKst, formatWon } from "@/lib/format";

export default function RunPage({ params }: PageProps<"/runs/[id]">) {
  return (
    <Suspense fallback={<Loading />}>
      <RunDetail params={params} />
    </Suspense>
  );
}

async function RunDetail({ params }: { params: PageProps<"/runs/[id]">["params"] }) {
  const runId = Number((await params).id);
  if (!Number.isInteger(runId)) notFound();
  const result = await api.GET("/runs/{run_id}", { params: { path: { run_id: runId } } });
  if (result.response.status === 404) notFound();
  const run = unwrap(result);
  const failed = run.results.filter((r) => r.status !== "ok");

  return (
    <>
      <Link href="/runs" className="text-sm text-zinc-500 hover:underline">
        ← 실행 이력
      </Link>
      <h1 className="mt-2 mb-6 flex items-center gap-3 text-2xl font-bold">
        실행 #{run.id} <StatusBadge status={run.status} />
      </h1>

      <dl className="mb-8 grid grid-cols-2 gap-4 rounded-lg border border-zinc-200 bg-white p-5 sm:grid-cols-4">
        <Item label="시작" value={formatKst(run.started_at)} />
        <Item label="걸린 시간" value={formatDuration(run.started_at, run.finished_at)} />
        <Item label="실행 방식" value={run.trigger === "schedule" ? "예약" : "수동"} />
        <Item label="성공" value={`${run.products_succeeded}/${run.products_total}`} />
      </dl>

      {run.error_message && (
        <p className="mb-6 rounded border border-amber-200 bg-amber-50 p-3 text-sm">{run.error_message}</p>
      )}

      {failed.length > 0 && (
        <Section title={`실패한 상품 ${failed.length}개`}>
          <ul className="space-y-2 text-sm">
            {failed.map((r) => (
              <li key={r.snapshot_id} className="rounded border border-red-200 bg-red-50 p-3">
                <span className="font-medium">{r.source_product_id}</span> <StatusBadge status={r.status} />
                <p className="mt-1 text-red-900">{r.error_message}</p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="상품별 결과">
        <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50 text-left text-xs text-zinc-500">
              <tr>
                <th className="px-4 py-2">상품(pcode)</th>
                <th className="px-4 py-2">상태</th>
                <th className="px-4 py-2">HTTP</th>
                <th className="px-4 py-2 text-right">최저가</th>
                <th className="px-4 py-2">메시지</th>
              </tr>
            </thead>
            <tbody>
              {run.results.map((r) => (
                <tr key={r.snapshot_id} className="border-b border-zinc-100 last:border-0">
                  <td className="px-4 py-2">
                    <Link href={`/products/${r.product_id}`} className="text-sky-700 hover:underline">
                      {r.source_product_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-4 py-2">{r.http_status ?? "-"}</td>
                  <td className="px-4 py-2 text-right">{formatWon(r.lowest_price)}</td>
                  {/* ok인데 메시지가 있으면 판매처 목록만 못 읽은 경우다 */}
                  <td className="px-4 py-2 text-zinc-500">{r.error_message ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-zinc-500">{label}</dt>
      <dd className="mt-1 text-sm">{value}</dd>
    </div>
  );
}
