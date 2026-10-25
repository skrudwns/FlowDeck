"use client";

import { useActionState } from "react";

import { addProduct, requestRun, setProductActive, updateSchedule, type ActionResult } from "@/app/actions";

// 백엔드 flowdeck.scheduler.INTERVAL_CHOICES와 같아야 한다. 다르면 API가 400으로 거절한다
const INTERVAL_CHOICES = [1, 2, 3, 4, 6, 8, 12, 24];

function Message({ state }: { state: ActionResult }) {
  if (!state) return null;
  return <p className={`mt-2 text-sm ${state.ok ? "text-emerald-700" : "text-red-700"}`}>{state.message}</p>;
}

export function RunButton({ jobId, blocked }: { jobId: string; blocked: string | null }) {
  const [state, action, pending] = useActionState(requestRun.bind(null, jobId), null);
  return (
    <form action={action}>
      <button
        disabled={pending || blocked !== null}
        className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:bg-zinc-300"
      >
        {pending ? "요청 중…" : "지금 실행"}
      </button>
      {blocked && !state && <p className="mt-2 text-sm text-zinc-500">{blocked}</p>}
      <Message state={state} />
    </form>
  );
}

export function ScheduleForm({
  jobId,
  intervalHours,
  enabled,
}: {
  jobId: string;
  intervalHours: number;
  enabled: boolean;
}) {
  const [state, action, pending] = useActionState(updateSchedule.bind(null, jobId), null);
  return (
    // React는 액션이 끝나면 폼을 처음 그릴 때의 기본값으로 되돌린다. 저장한 값으로 다시 그리게 key를 바꾼다
    <form key={`${intervalHours}-${enabled}`} action={action} className="text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2">
          주기
          <select
            name="interval_hours"
            defaultValue={intervalHours}
            className="rounded border border-zinc-300 bg-white px-2 py-1"
          >
            {INTERVAL_CHOICES.map((h) => (
              <option key={h} value={h}>
                {h === 1 ? "매시" : `${h}시간마다`}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" name="enabled" defaultChecked={enabled} />
          정기 실행
        </label>
        <button disabled={pending} className="rounded border border-zinc-300 bg-white px-3 py-1 hover:bg-zinc-50">
          {pending ? "저장 중…" : "저장"}
        </button>
      </div>
      <Message state={state} />
    </form>
  );
}

export function AddProductForm() {
  const [state, action, pending] = useActionState(addProduct, null);
  return (
    <form action={action} className="text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <input
          name="pcode"
          required
          inputMode="numeric"
          placeholder="다나와 pcode"
          className="w-40 rounded border border-zinc-300 bg-white px-3 py-1.5"
        />
        <button disabled={pending} className="rounded bg-zinc-900 px-3 py-1.5 text-white disabled:bg-zinc-300">
          {pending ? "추가 중…" : "수집 대상 추가"}
        </button>
      </div>
      <Message state={state} />
    </form>
  );
}

export function ProductToggle({ productId, active }: { productId: number; active: boolean }) {
  const [state, action, pending] = useActionState(setProductActive.bind(null, productId, !active), null);
  return (
    <form action={action}>
      <button disabled={pending} className="text-xs text-sky-700 hover:underline disabled:text-zinc-400">
        {active ? "중지" : "재개"}
      </button>
      {state && !state.ok && <p className="text-xs text-red-700">{state.message}</p>}
    </form>
  );
}
