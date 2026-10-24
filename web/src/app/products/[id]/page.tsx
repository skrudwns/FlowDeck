import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { PriceChart } from "@/components/price-chart";
import { Loading, Section } from "@/components/section";
import { StatusBadge } from "@/components/status-badge";
import { api, unwrap, type PricePoint } from "@/lib/api/client";
import { formatKst, formatKstShort, formatWon, sourceLabel } from "@/lib/format";

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

  // 판매처는 가장 최근의 정상 수집 기준
  const latestOk = [...prices].reverse().find((p) => p.status === "ok");
  const sellers = latestOk
    ? unwrap(await api.GET("/snapshots/{snapshot_id}/sellers", { params: { path: { snapshot_id: latestOk.snapshot_id } } }))
    : [];

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
        <PriceChart points={prices.map((p) => ({ label: formatKstShort(p.collected_at), price: p.lowest_price }))} />
      </Section>

      <Section title={latestOk ? `판매처 가격 (${formatKst(latestOk.collected_at)} 수집)` : "판매처 가격"}>
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
              </tr>
            </thead>
            <tbody>
              {sellers.map((s) => (
                // 품절 판매처는 최저가와 판매처 수에 들어가지 않는다 (ADR-0010)
                <tr key={s.rank} className={`border-b border-zinc-100 last:border-0 ${s.in_stock ? "" : "text-zinc-400"}`}>
                  <td className="px-4 py-2">{s.rank}</td>
                  <td className="px-4 py-2">{s.seller_name}</td>
                  <td className="px-4 py-2 text-right">{formatWon(s.price)}</td>
                  <td className="px-4 py-2 text-right">{s.delivery_fee === 0 ? "무료" : formatWon(s.delivery_fee)}</td>
                  <td className="px-4 py-2">{s.in_stock ? "있음" : "품절"}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
