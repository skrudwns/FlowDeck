import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { PriceChart } from "@/components/price-chart";
import { Loading, Section } from "@/components/section";
import { StatusBadge } from "@/components/status-badge";
import { api, unwrap, type PriceChange, type PricePoint, type SellerSignal } from "@/lib/api/client";
import { formatKst, formatKstShort, formatPct, formatWon, sourceLabel } from "@/lib/format";

export default function ProductPage({ params }: PageProps<"/products/[id]">) {
  return (
    <Suspense fallback={<Loading />}>
      <ProductDetail params={params} />
    </Suspense>
  );
}

async function ProductDetail({ params }: { params: PageProps<"/products/[id]">["params"] }) {
  const productId = Number((await params).id);
  if (!Number.isInteger(productId)) notFound();

  const productResult = await api.GET("/products/{product_id}", { params: { path: { product_id: productId } } });
  if (productResult.response.status === 404) notFound();
  const product = unwrap(productResult);
  const prices = unwrap(
    await api.GET("/products/{product_id}/prices", { params: { path: { product_id: productId } } }),
  );

  const latestOk = [...prices].reverse().find((p) => p.status === "ok");
  // 판매처 가격과 위치는 판매처 목록이 있는 가장 최근 수집 기준 (ADR-0014)
  const signals = unwrap(
    await api.GET("/products/{product_id}/signals", { params: { path: { product_id: productId } } }),
  );
  const sellers = signals.sellers;

  return (
    <>
      <Link href="/products" className="text-sm text-zinc-500 hover:underline">
        ← 상품 가격
      </Link>
      <h1 className="mt-2 text-2xl font-bold">{product.name ?? product.source_product_id}</h1>
      <p className="mb-6 text-sm text-zinc-500">
        {sourceLabel(product.source)} {product.source === "danawa" ? "pcode" : "상품 코드"} {product.source_product_id} ·
        수집 {prices.length}회
      </p>

      <dl className="mb-8 grid grid-cols-2 gap-4 rounded-lg border border-zinc-200 bg-white p-5 sm:grid-cols-4">
        <Item label="최근 최저가" value={formatWon(latestOk?.lowest_price)} />
        <Item label="판매처 수" value={String(latestOk?.offer_count ?? "-")} />
        <Item label="기간 최저" value={formatWon(minPrice(prices))} />
        <Item label="기간 최고" value={formatWon(maxPrice(prices))} />
      </dl>

      <Section title="최저가 추이">
        <PriceChart
          points={prices.map((p) => ({ label: formatKstShort(p.collected_at), price: p.lowest_price }))}
          markers={signals.changes.map((c) => formatKstShort(c.at))}
        />
      </Section>

      <Section title={`최저가 변화 (최근 ${CHANGE_DAYS}일)`}>
        <Changes changes={signals.changes} rules={signals.rules} />
      </Section>

      <Section
        title={
          signals.sellers_collected_at ? `판매처 가격 (${formatKst(signals.sellers_collected_at)} 수집)` : "판매처 가격"
        }
      >
        {sellers.length === 0 ? (
          <p className="text-sm text-zinc-500">판매처 목록이 없다</p>
        ) : (
          <table className="w-full rounded-lg border border-zinc-200 bg-white text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50 text-left text-xs text-zinc-500">
              <tr>
                <th className="px-4 py-2">순위</th>
                <th className="px-4 py-2">판매처</th>
                <th className="px-4 py-2 text-right">가격</th>
                <th className="px-4 py-2 text-right">배송비</th>
                <th className="px-4 py-2">재고</th>
                <th className="px-4 py-2 text-right">다른 판매처 대비</th>
                <th className="px-4 py-2 text-right">평소 가격 대비</th>
              </tr>
            </thead>
            <tbody>
              {sellers.map((s) => (
                // 품절 판매처는 최저가와 판매처 수에 들어가지 않는다 (ADR-0010)
                <tr key={s.rank} className={`border-b border-zinc-100 last:border-0 ${s.in_stock ? "" : "text-zinc-400"}`}>
                  <td className="px-4 py-2">{s.rank}</td>
                  <td className="px-4 py-2">{s.seller_name}</td>
                  <td className="px-4 py-2 text-right">
                    {/* 현금가는 다나와 최저가 계산에서 빠지고 목록도 가격순이 아니다 (#33) */}
                    {s.price_label === "현금" && (
                      <span className="mr-2 rounded bg-zinc-100 px-1.5 py-0.5 text-xs text-zinc-600">현금</span>
                    )}
                    {formatWon(s.price)}
                  </td>
                  <td className="px-4 py-2 text-right">{s.delivery_fee === 0 ? "무료" : formatWon(s.delivery_fee)}</td>
                  <td className="px-4 py-2">{s.in_stock ? "있음" : "품절"}</td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">
                    <Position pct={s.vs_others_pct} cheaper={s.cheaper_than_others} badge="다른 곳보다 쌈" />
                  </td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">
                    <Position pct={s.vs_usual_pct} cheaper={s.cheaper_than_usual} badge="평소보다 쌈" />
                    <UsualPrice seller={s} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {sellers.length > 0 && (
          // 가격만으로는 할인을 절반 정도만 잡는다 (AN-0004). "할인 아님"으로 읽히지 않게 적는다
          <p className="mt-2 text-xs text-zinc-500">
            다른 판매처 대비는 재고 있는 다른 판매처(현금가 제외) 가격의 중앙값, 평소 가격은 이 판매처의 지난{" "}
            {signals.rules.usual_days}일 가격 중앙값과 비교했다. {signals.rules.cheaper_min_pct}% 이상 싸면 표시한다.
            가격만 보고 낸 값이라 판매처가 붙인 할인 표시와 다를 수 있고, 표시가 없다고 할인이 아닌 것은 아니다.
          </p>
        )}
      </Section>

      <Section title="수집 이력">
        <table className="w-full rounded-lg border border-zinc-200 bg-white text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-left text-xs text-zinc-500">
            <tr>
              <th className="px-4 py-2">시각</th>
              <th className="px-4 py-2">상태</th>
              <th className="px-4 py-2 text-right">최저가</th>
              <th className="px-4 py-2 text-right">판매처 수</th>
            </tr>
          </thead>
          <tbody>
            {[...prices].reverse().map((p) => (
              <tr key={p.snapshot_id} className="border-b border-zinc-100 last:border-0">
                <td className="px-4 py-2 whitespace-nowrap">{formatKst(p.collected_at)}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={p.status} />
                </td>
                <td className="px-4 py-2 text-right">{formatWon(p.lowest_price)}</td>
                <td className="px-4 py-2 text-right">{p.offer_count ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </>
  );
}

// API 기본값과 같다
const CHANGE_DAYS = 7;

function Changes({
  changes,
  rules,
}: {
  changes: PriceChange[];
  rules: { change_min_pct: number; change_persist: number };
}) {
  const note = (
    <p className="mt-2 text-xs text-zinc-500">
      직전 수준(마지막 변화 뒤 최저가의 중앙값)보다 {rules.change_min_pct}% 이상 바뀐 최저가가 {rules.change_persist}번
      연속 수집되면 변화로 본다. 한 번만 튀었다 돌아온 가격은 넣지 않는다.
    </p>
  );
  if (changes.length === 0) {
    return (
      <>
        <p className="text-sm text-zinc-500">기간 안에 기준을 넘은 변화가 없다</p>
        {note}
      </>
    );
  }
  return (
    <>
      <table className="w-full rounded-lg border border-zinc-200 bg-white text-sm">
        <thead className="border-b border-zinc-200 bg-zinc-50 text-left text-xs text-zinc-500">
          <tr>
            <th className="px-4 py-2">시각</th>
            <th className="px-4 py-2 text-right">직전 수준</th>
            <th className="px-4 py-2 text-right">새 최저가</th>
            <th className="px-4 py-2 text-right">변화</th>
          </tr>
        </thead>
        <tbody>
          {[...changes].reverse().map((c) => (
            <tr key={c.at} className="border-b border-zinc-100 last:border-0">
              <td className="px-4 py-2 whitespace-nowrap">{formatKst(c.at)}</td>
              <td className="px-4 py-2 text-right">{formatWon(c.before)}</td>
              <td className="px-4 py-2 text-right">{formatWon(c.after)}</td>
              <td className={`px-4 py-2 text-right ${c.pct < 0 ? "text-sky-700" : "text-rose-700"}`}>
                {c.pct < 0 ? "▼" : "▲"} {formatPct(c.pct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {note}
    </>
  );
}

function Position({ pct, cheaper, badge }: { pct: number | null; cheaper: boolean; badge: string }) {
  return (
    <>
      {cheaper && <span className="mr-2 rounded bg-sky-50 px-1.5 py-0.5 text-xs text-sky-700">{badge}</span>}
      <span className={pct == null ? "text-zinc-400" : ""}>{formatPct(pct)}</span>
    </>
  );
}

function UsualPrice({ seller }: { seller: SellerSignal }) {
  if (seller.usual_price == null) return null;
  return <div className="text-xs text-zinc-500">{formatWon(seller.usual_price)}</div>;
}

function minPrice(prices: PricePoint[]) {
  const values = prices.map((p) => p.lowest_price).filter((v): v is number => v != null);
  return values.length ? Math.min(...values) : null;
}

function maxPrice(prices: PricePoint[]) {
  const values = prices.map((p) => p.lowest_price).filter((v): v is number => v != null);
  return values.length ? Math.max(...values) : null;
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-zinc-500">{label}</dt>
      <dd className="mt-1 text-sm">{value}</dd>
    </div>
  );
}
