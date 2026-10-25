"use server";

import { refresh } from "next/cache";

import { api } from "@/lib/api/client";

// 포털 제어 동작 (ADR-0011). 웹은 API를 서버에서만 부른다 (ADR-0009).
// 인증이 없다. 포털을 로컬에서만 띄우기 때문이고, 배포 전에 넣어야 한다.

export type ActionResult = { ok: boolean; message: string } | null;

function failure(error: unknown, status: number): ActionResult {
  const detail =
    error && typeof error === "object" && "detail" in error && typeof error.detail === "string"
      ? error.detail
      : `요청 실패 (HTTP ${status})`;
  return { ok: false, message: detail };
}

// useActionState가 이전 상태와 폼 데이터를 넘기지만 쓰지 않아서 받지 않는다
export async function requestRun(jobId: string): Promise<ActionResult> {
  const { data, error, response } = await api.POST("/jobs/{job_id}/run-requests", {
    params: { path: { job_id: jobId } },
  });
  if (!data) return failure(error, response.status);
  refresh();
  if (data.dispatch_error) {
    // 바로 실행하지 않은 이유와 그 뒤에 어떻게 되는지가 문장으로 온다 (로컬 DB, GitHub 오류)
    return { ok: true, message: `요청을 남겼다. ${data.dispatch_error}` };
  }
  if (!data.dispatched_at) {
    return { ok: true, message: "요청을 남겼다. GitHub 토큰이 없어서 다음 정기 호출 때 돈다" };
  }
  return { ok: true, message: "실행을 요청했다. GitHub Actions 준비 시간 뒤에 시작한다" };
}

export async function updateSchedule(jobId: string, _prev: ActionResult, form: FormData): Promise<ActionResult> {
  const { data, error, response } = await api.PATCH("/jobs/{job_id}", {
    params: { path: { job_id: jobId } },
    body: { interval_hours: Number(form.get("interval_hours")), enabled: form.get("enabled") === "on" },
  });
  if (!data) return failure(error, response.status);
  refresh();
  return { ok: true, message: `저장했다: ${data.schedule}${data.enabled ? "" : ", 꺼짐"}` };
}

export async function addProduct(_prev: ActionResult, form: FormData): Promise<ActionResult> {
  const pcode = String(form.get("pcode") ?? "").trim();
  const { data, error, response } = await api.POST("/products", { body: { source_product_id: pcode } });
  if (!data) return failure(error, response.status);
  refresh();
  return { ok: true, message: `${pcode}을 수집 대상에 넣었다. 이름은 다음 수집 때 채워진다` };
}

export async function setProductActive(productId: number, active: boolean): Promise<ActionResult> {
  const { data, error, response } = await api.PATCH("/products/{product_id}", {
    params: { path: { product_id: productId } },
    body: { active },
  });
  if (!data) return failure(error, response.status);
  refresh();
  return { ok: true, message: active ? "재개했다" : "중지했다" };
}
