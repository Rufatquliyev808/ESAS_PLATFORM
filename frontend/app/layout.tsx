import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ESAS Platform — Monitorinq",
  description: "MT5 məlumat axını və çatdırılma vəziyyətinin canlı monitorinqi.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="az">
      <body>{children}</body>
    </html>
  );
}
