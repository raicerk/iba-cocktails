import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "IBA Cocktails App",
  description: "Encuentra y descubre cócteles increíbles.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className={inter.className}>
        <nav className="bg-slate-900 text-white p-4 shadow-md">
          <div className="max-w-6xl mx-auto flex gap-6 items-center">
            <Link href="/" className="font-bold text-xl tracking-tight">🍸 IBA Cocktails</Link>
            <Link href="/cocktails" className="hover:text-blue-300 transition">Catálogo</Link>
            <Link href="/rag" className="hover:text-blue-300 transition">IA Bartender</Link>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}