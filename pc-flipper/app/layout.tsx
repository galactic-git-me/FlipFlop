import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { BackendStatus } from "@/components/backend-status";
import { TraeBg } from "@/components/trae-bg";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PC Flip Profit Maximizer",
  description: "AI-powered PC flipping intelligence platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="h-full flex overflow-hidden bg-[#080c14]">
        <TraeBg />
        <Sidebar />
        <main className="flex-1 overflow-y-auto relative">
          {children}
        </main>
        <BackendStatus />
      </body>
    </html>
  );
}
