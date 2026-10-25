import Link from "next/link";
import { Suspense } from "react";

import { AddProductForm, ProductToggle } from "@/components/controls";
import { Loading } from "@/components/section";
import { StatusBadge } from "@/components/status-badge";
import { api, unwrap } from "@/lib/api/client";
import { formatKst, formatWon, sourceLabel } from "@/lib/format";

type Search = PageProps<"/products">["searchParams"];

const SOURCE_FILTERS = [
  { value: "", label: "모든 수집 대상" },
  { value: "danawa", label: "다나와" },
  { value: "mockshop", label: "연습 쇼핑몰" },
];

const ACTIVE_FILTERS = [
  { value: "", label: "수집 중" },
  { value: "inactive", label: "중지됨" },
  { value: "all", label: "전체 상품" },
];

const STATUS_FILTERS = [
  { value: "", label: "전체" },
  { value: "ok", label: "정상" },
  { value: "failed", label: "실패" },
];

export default function ProductsPage({ searchParams }: PageProps<"/products">) {
  return (
    <>
      <h1 className="mb-6 text-2xl font-bold">상품 가격</h1>
      <div className="mb-6 rounded-lg border border-zinc-200 bg-white p-4">
        <p className="mb-2 text-xs text-zinc-500">
          다나와 수집 대상은 30개까지. 연습 쇼핑몰 상품은 쇼핑몰 목록으로 정해진다.
        </p>
        <AddProductForm />
      </div>
      <Suspense fallback={<Loading />}>
        <ProductsTable searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function ProductsTable({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  const q = typeof params.q === "string" ? params.q.trim() : "";
  const status = typeof params.status === "string" ? params.status : "";
  const source = typeof params.source === "string" ? params.source : "";
  const shown = typeof params.shown === "string" ? params.shown : "";

  // 수집 대상은 수십 개라 한 번에 받아서 거른다. 많아지면 API에 검색을 넣는다
  const everything = unwrap(await api.GET("/products", { params: { query: { limit: 500 } } }));
  const all = everything.filter((p) => (shown === "all" ? true : shown === "inactive" ? !p.active : p.active));
  const products = all.filter((p) => {
    const text = `${p.name ?? ""} ${p.source_product_id}`.toLowerCase();
    if (q && !text.includes(q.toLowerCase())) return false;
    if (source && p.source !== source) return false;
    if (status === "ok" && p.latest?.status !== "ok") return false;
    if (status === "failed" && (!p.latest || p.latest.status === "ok")) return false;
    return true;
  });

  return (
    <>
      <form className="mb-4 flex flex-wrap items-center gap-2 text-sm">
        <input
          name="q"
          defaultValue={q}
          placeholder="상품 이름 또는 상품 코드"
          className="w-64 rounded border border-zinc-300 bg-white px-3 py-1.5"
        />
        <select name="source" defaultValue={source} className="rounded border border-zinc-300 bg-white px-2 py-1.5">
          {SOURCE_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
        <select name="shown" defaultValue={shown} className="rounded border border-zinc-300 bg-white px-2 py-1.5">
          {ACTIVE_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
        <select name="status" defaultValue={status} className="rounded border border-zinc-300 bg-white px-2 py-1.5">
          {STATUS_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
        <button className="rounded bg-zinc-900 px-3 py-1.5 text-white">검색</button>
        <span className="text-zinc-500">
          {products.length}/{all.length}개
        </span>
      </form>

      <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-left text-xs text-zinc-500">
            <tr>
              <th className="px-4 py-2">상품</th>
              <th className="px-4 py-2 text-right">최저가</th>
              <th className="px-4 py-2 text-right">판매처 수</th>
              <th className="px-4 py-2">최근 상태</th>
              <th className="px-4 py-2">수집 시각</th>
              <th className="px-4 py-2">수집 대상</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50">
                <td className="px-4 py-2">
                  <Link href={`/products/${p.id}`} className="text-sky-700 hover:underline">
                    {p.name ?? p.source_product_id}
                  </Link>
                  <span className="ml-2 text-xs text-zinc-400">
                    {sourceLabel(p.source)} {p.source_product_id}
                  </span>
                </td>
                <td className="px-4 py-2 text-right whitespace-nowrap">{formatWon(p.latest?.lowest_price)}</td>
                <td className="px-4 py-2 text-right">{p.latest?.offer_count ?? "-"}</td>
                <td className="px-4 py-2">{p.latest ? <StatusBadge status={p.latest.status} /> : "-"}</td>
                <td className="px-4 py-2 whitespace-nowrap">{formatKst(p.latest?.collected_at)}</td>
                <td className="px-4 py-2 whitespace-nowrap">
                  <span className={p.active ? "" : "text-zinc-400"}>{p.active ? "수집 중" : "중지됨"}</span>
                  {p.source === "danawa" && (
                    <span className="ml-2 inline-block">
                      <ProductToggle productId={p.id} active={p.active} />
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {products.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-zinc-500">
                  조건에 맞는 상품이 없다
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
