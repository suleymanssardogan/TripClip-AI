import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans, Playfair_Display } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-jakarta",
});
const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair",
  weight: ["400", "700", "800", "900"],
});

export const metadata: Metadata = {
  title: "TripClip AI | Gezi Planı Oluştur",
  description: "Gezi videolarını akıllı seyahat rotalarına dönüştür.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr" className="dark">
      <body
        className={`${inter.variable} ${jakarta.variable} ${playfair.variable} font-sans bg-bg text-ice antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
