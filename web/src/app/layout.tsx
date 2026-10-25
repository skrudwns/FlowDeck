import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "FlowDeck",
  description: "수집 자동화 작업과 결과를 관리하는 포털",
};

const NAV = [
  { href: "/", label: "작업" },
  { href: "/runs", label: "실행 이력" },
  { href: "/products", label: "상품 가격" },
  { href: "/activity", label: "변경 이력" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full bg-zinc-50 text-zinc-900">
        <header className="border-b border-zinc-200 bg-white">
          <nav className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
            <Link href="/" className="font-semibold">
              FlowDeck
            </Link>
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className="text-sm text-zinc-600 hover:text-zinc-900">
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
