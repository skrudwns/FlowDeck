"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts";

export type ChartPoint = { label: string; price: number | null };

const won = new Intl.NumberFormat("ko-KR");

/**
 * 최저가 선 그래프. 실패한 수집은 price가 null이라 선이 끊겨서 빈 구간이 보인다.
 * markers는 최저가 변화가 잡힌 수집의 label이다. 세로 점선으로 표시한다.
 */
export function PriceChart({ points, markers = [] }: { points: ChartPoint[]; markers?: string[] }) {
  if (points.length === 0) {
    return <p className="text-sm text-zinc-500">아직 수집된 가격이 없다</p>;
  }
  return (
    <div className="h-72 w-full rounded-lg border border-zinc-200 bg-white p-4">
      <LineChart data={points} responsive style={{ width: "100%", height: "100%" }}>
        <CartesianGrid stroke="#f4f4f5" />
        <XAxis dataKey="label" tick={{ fontSize: 12 }} minTickGap={24} />
        <YAxis
          tick={{ fontSize: 12 }}
          width={80}
          domain={["auto", "auto"]}
          tickFormatter={(v: number) => won.format(v)}
        />
        <Tooltip formatter={(v) => [`${won.format(Number(v))}원`, "최저가"]} />
        {markers.map((label) => (
          <ReferenceLine key={label} x={label} stroke="#a1a1aa" strokeDasharray="4 4" />
        ))}
        {/* 가격은 다음 수집 전까지 유지된 값이라 계단형으로 그린다. 점이 적으면 점도 찍는다 */}
        <Line
          type="stepAfter"
          dataKey="price"
          stroke="#0369a1"
          dot={points.length <= 48}
          connectNulls={false}
        />
      </LineChart>
    </div>
  );
}
