import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "How to Master Codeforces",
  description: "Data-driven insights from top competitive programmers",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex">{children}</body>
    </html>
  );
}
