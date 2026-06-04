import type { Metadata } from "next";
import { Rajdhani, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { BackendStatus } from "@/components/backend-status";
import { TraeBg } from "@/components/trae-bg";
import { FacebookCookieBanner } from "@/components/facebook-cookie-banner";
import { TopCommandBar } from "@/components/top-command-bar";
import { FaviconAnimator } from "@/components/favicon-animator";

const rajdhani = Rajdhani({
  variable: "--font-rajdhani",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "FlipFlop",
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
      className={`${rajdhani.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="h-full node-body" suppressHydrationWarning>
        <FaviconAnimator />
        <TraeBg />
        <Sidebar />

        <div className="node-main-wrap">
          <TopCommandBar />
          <main className="node-content">
            <FacebookCookieBanner />
            {children}
          </main>
        </div>

        <BackendStatus />
      </body>
    </html>
  );
}
