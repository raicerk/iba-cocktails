"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

export default function CocktailDetailPage() {
  const params = useParams();
  const slug = params?.slug as string;

  const [cocktail, setCocktail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!slug) return;

    const fetchDetail = async () => {
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/${slug}`);
        if (!res.ok) throw new Error("404");
        const data = await res.json();
        setCocktail(data);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    fetchDetail();
  }, [slug]);

  if (loading) {
    return <main className="p-6 text-center text-gray-500">Cargando receta...</main>;
  }

  if (error || !cocktail) {
    return (
      <main className="p-6 text-center">
        <p className="text-red-500 font-semibold text-lg mb-4">Cóctel no encontrado.</p>
        <Link href="/" className="text-blue-600 underline">
          ← Volver al catálogo
        </Link>
      </main>
    );
  }

  return (
    <main className="max-w-3xl mx-auto p-6">
      <Link href="/" className="text-sm text-blue-600 hover:underline mb-4 inline-block">
        ← Volver al catálogo
      </Link>

      <h1 className="text-4xl font-bold mb-2 text-slate-900">{cocktail.name}</h1>
      <p className="text-blue-600 font-medium mb-6">{cocktail.category}</p>

      {cocktail.image_url && (
        <img
          src={cocktail.image_url}
          alt={cocktail.name}
          className="w-full h-72 object-cover rounded-xl mb-6 shadow-sm"
        />
      )}

      <div className="mb-6 bg-slate-50 p-4 rounded-lg border">
        <h2 className="text-xl font-bold mb-3 text-slate-800">Ingredientes:</h2>
        <ul className="list-disc list-inside space-y-1 text-gray-700">
          {cocktail.ingredients?.map((i: any, idx: number) => (
            <li key={idx}>
              {i.original || `${i.quantity || ""} ${i.unit || ""} ${i.ingredient}`}
            </li>
          ))}
        </ul>
      </div>

      <div className="mb-6">
        <h2 className="text-xl font-bold mb-2 text-slate-800">Preparación:</h2>
        <p className="text-gray-700 whitespace-pre-line leading-relaxed">{cocktail.method}</p>
      </div>

      {cocktail.garnish && cocktail.garnish !== "N/A" && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <h2 className="text-lg font-bold mb-1 text-amber-900">Decoración:</h2>
          <p className="text-amber-800">{cocktail.garnish}</p>
        </div>
      )}
    </main>
  );
}