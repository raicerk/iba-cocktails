"use client";

import { useState } from "react";
import Link from "next/link";

interface Ingredient {
  ingredient: string;
  quantity?: number;
  unit?: string;
}

interface Cocktail {
  name: string;
  slug: string;
  category: string;
  image_url?: string;
  ingredients: Ingredient[];
}

export default function RagPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [recommendedCocktails, setRecommendedCocktails] = useState<Cocktail[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setAnswer("");
    setRecommendedCocktails([]);
    setError("");

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/rag`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      if (!res.ok) throw new Error("Error al consultar el servicio RAG");

      const data = await res.json();
      setAnswer(data.answer);
      setRecommendedCocktails(data.cocktails || []);
    } catch (err: any) {
      setError(err.message || "Ocurrió un error al procesar la respuesta.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="max-w-6xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-2 text-center text-slate-800">IA Bartender 🤖🍸</h1>
      <p className="text-gray-600 mb-6 text-center">
        Consulta qué cóctel preparar según tus gustos e ingredientes disponibles.
      </p>

      {/* Formulario de Consulta */}
      <form onSubmit={handleAsk} className="flex flex-col gap-4 max-w-2xl mx-auto mb-8">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ej: ¿Qué cóctel refrescante con gin o campari me recomiendas?"
          className="p-3 border rounded-xl resize-none text-black h-28 focus:ring-2 focus:ring-blue-500 outline-none shadow-sm"
          required
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl transition-colors disabled:bg-gray-400"
        >
          {loading ? "Mezclando respuesta..." : "Consultar Bartender"}
        </button>
      </form>

      {/* Mensaje de Error */}
      {error && <p className="text-red-500 mb-6 text-center">{error}</p>}

      {/* Respuesta de la IA justo debajo del input */}
      {answer && (
        <div className="p-6 bg-slate-50 border border-slate-200 rounded-xl mb-10 shadow-sm max-w-4xl mx-auto">
          <h2 className="text-lg font-bold mb-2 text-slate-900 flex items-center gap-2">
            <span>🤖</span> Respuesta del Bartender:
          </h2>
          <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{answer}</p>
        </div>
      )}

      {/* Listado de Cócteles Recomendados en formato Grid/Cards */}
      {recommendedCocktails.length > 0 && (
        <div>
          <h2 className="text-2xl font-bold mb-6 text-slate-800 border-b pb-2">
            Cócteles Relacionados ({recommendedCocktails.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {recommendedCocktails.map((c) => (
              <div
                key={c.slug}
                className="border rounded-xl overflow-hidden shadow-sm hover:shadow-md transition bg-white flex flex-col justify-between"
              >
                <div>
                  {c.image_url && (
                    <img src={c.image_url} alt={c.name} className="w-full h-48 object-cover" />
                  )}
                  <div className="p-4">
                    <span className="text-xs font-bold text-blue-600 uppercase">{c.category}</span>
                    <h3 className="text-xl font-bold text-gray-900 mt-1">{c.name}</h3>
                    <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                      Ingredientes: {c.ingredients?.map((i) => i.ingredient).join(", ")}
                    </p>
                  </div>
                </div>
                <div className="p-4 pt-0">
                  <Link
                    href={`/cocktails/${c.slug}`}
                    className="inline-block text-blue-600 font-semibold hover:underline"
                  >
                    Ver Receta Completa →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}