import "server-only";

import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

// 서버 컴포넌트에서만 부른다. API 주소는 브라우저에 드러나지 않는다 (ADR-0009)
const baseUrl = process.env.FLOWDECK_API_URL ?? "http://localhost:8000";

export const api = createClient<paths>({ baseUrl });

export type Schemas = components["schemas"];
export type Job = Schemas["JobOut"];
export type Run = Schemas["RunOut"];
export type RunDetail = Schemas["RunDetail"];
export type Product = Schemas["ProductOut"];
export type PricePoint = Schemas["PricePoint"];
export type Seller = Schemas["SellerOut"];

/** 응답에 오류가 있으면 던진다. 화면은 error.tsx가 받는다. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined) {
    throw new Error(`API ${result.response.status} ${result.response.url}`);
  }
  return result.data;
}
