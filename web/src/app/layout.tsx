import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jakarta = Plus_Jakarta_Sans({ 
  subsets: ["latin"], 
  variable: "--font-jakarta" 
});

export const metadata: Metadata = {
  title: "TripClip AI | Visual Guide",
  description: "Reels videolarını akıllı seyahat rotalarına dönüştür.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr" className="dark">
      <head>
        {/* Material Symbols for some legacy components */}
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" />
      </head>
      <body className={`${inter.variable} ${jakarta.variable} font-body bg-surface text-on-surface antialiased`}>
        {children}
      </body>
    </html>
  );
}
