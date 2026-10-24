"use client";

import { useEffect } from "react";

// 오류 경계는 클라이언트 컴포넌트여야 한다. Next.js 16은 다시 시도 함수를 retry로 넘긴다
export default function ErrorPage({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-6">
      <h2 className="font-semibold text-red-900">데이터를 불러오지 못했다</h2>
      <p className="mt-2 text-sm text-red-800">
        API 서버가 꺼져 있거나 주소(FLOWDECK_API_URL)가 맞지 않을 수 있다.
      </p>
      <button
        onClick={() => retry()}
        className="mt-4 rounded bg-red-900 px-3 py-1.5 text-sm text-white hover:bg-red-800"
      >
        다시 시도
      </button>
    </div>
  );
}
