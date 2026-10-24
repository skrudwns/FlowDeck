import Link from "next/link";
import { Suspense } from "react";

import { Loading, Section } from "@/components/section";
import { StatusBadge } from "@/components/status-badge";
import { api, unwrap, type Job, type RunDetail } from "@/lib/api/client";
import { formatDuration, formatKst } from "@/lib/format";

export default function HomePage() {
  return (
    <>
      <h1 className="mb-8 text-2xl font-bold">작업</h1>
      {/* 요청마다 새로 가져오는 데이터라 Suspense로 감싼다 (Next.js Cache Components) */}
      <Suspense fallback={<Loading />}>
        <Jobs />
      </Suspense>
    </>
  );
}

async function Jobs() {
  const jobs = unwrap(await api.GET("/jobs"));
  return (
    <>
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} />
      ))}
    </>
  );
}

async function JobCard({ job }: { job: Job }) {
  const lastRun = job.last_run
    ? unwrap(await api.GET("/runs/{run_id}", { params: { path: { run_id: job.last_run.id } } }))
    : null;
  return (
    <div>
      <Section title={job.name}>
        <dl className="grid grid-cols-2 gap-4 rounded-lg border border-zinc-200 bg-white p-5 sm:grid-cols-4">
          <Item label="주기" value={job.schedule} />
          <Item label="다음 실행" value={formatKst(job.next_run_at)} />
          <Item label="수집 대상" value={`상품 ${job.active_products}개`} />
          <div>
            <dt className="text-xs text-zinc-500">마지막 실행</dt>
            <dd className="mt-1 text-sm">
              {lastRun ? (
                <Link href={`/runs/${lastRun.id}`} className="flex items-center gap-2 hover:underline">
                  <StatusBadge status={lastRun.status} />
                  {formatKst(lastRun.started_at)}
                </Link>
              ) : (
                "아직 없음"
              )}
            </dd>
          </div>
        </dl>
        <p className="mt-2 text-sm text-zinc-500">{job.description}</p>
      </Section>
      <Section title="흐름">
        <Flow run={lastRun} />
      </Section>
    </div>
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

type Stage = { name: string; detail: string; status: "ok" | "failed" | "partial" | "unknown"; note: string };

/** 마지막 실행 결과로 단계별 상태를 보여준다. 알림 단계 결과는 Healthchecks.io에만 있어서 여기서는 알 수 없다. */
function Flow({ run }: { run: RunDetail | null }) {
  const results = run?.results ?? [];
  const requestFailed = results.filter((r) => ["http_error", "blocked", "disallowed"].includes(r.status)).length;
  const parseFailed = results.filter((r) => r.status === "parse_failed").length;
  const saved = results.length;

  const stages: Stage[] = [
    {
      name: "수집",
      detail: "다나와 상품 페이지 요청",
      status: !run ? "unknown" : requestFailed === 0 ? "ok" : requestFailed === results.length ? "failed" : "partial",
      note: run ? `요청 실패 ${requestFailed}개` : "",
    },
    {
      name: "가공",
      detail: "최저가·판매처 파싱",
      status: !run ? "unknown" : parseFailed === 0 ? "ok" : "partial",
      note: run ? `파싱 실패 ${parseFailed}개` : "",
    },
    {
      name: "저장",
      detail: "Postgres",
      status: !run ? "unknown" : run.finished_at ? "ok" : "failed",
      note: run ? `결과 ${saved}건 기록, ${formatDuration(run.started_at, run.finished_at)}` : "",
    },
    {
      name: "알림",
      detail: "Healthchecks.io 신호",
      status: "unknown",
      note: "결과는 Healthchecks.io에서 확인",
    },
  ];

  const color = {
    ok: "border-emerald-300 bg-emerald-50",
    partial: "border-amber-300 bg-amber-50",
    failed: "border-red-300 bg-red-50",
    unknown: "border-zinc-200 bg-white",
  };

  return (
    <ol className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
      {stages.map((stage, i) => (
        <li key={stage.name} className="flex flex-1 items-center gap-2">
          <div className={`flex-1 rounded-lg border p-4 ${color[stage.status]}`}>
            <p className="font-medium">{stage.name}</p>
            <p className="text-xs text-zinc-600">{stage.detail}</p>
            {stage.note && <p className="mt-2 text-xs text-zinc-500">{stage.note}</p>}
          </div>
          {i < stages.length - 1 && <span className="hidden text-zinc-400 sm:inline">→</span>}
        </li>
      ))}
    </ol>
  );
}
