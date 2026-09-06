"use client";

import { useState } from "react";

export default function RagPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [recommendedCocktails, setRecommendedCocktails] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setAnswer("");
    setRecommendedCocktails([]);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/rag`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      const data = await res.json();
      setAnswer(data.answer);
      setRecommendedCocktails(data.cocktails || []);
    } catch (error) {
      setAnswer("Ocurrió un error al procesar la respuesta.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="max-w-4xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-4 text-center">IA Bartender 🤖🍸</h1>
      
      <form onSubmit={handleAsk} className="flex flex-col gap-4 mb-8">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ej: ¿Qué cóctel refrescante con gin o campari me recomiendas?"
          className="p-3 border rounded-lg resize-none text-black h-28 focus:ring-2 focus:ring-blue-500"
          required
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-lg disabled:bg-gray-400"
        >
          {loading ? "Pensando..." : "Consultar Bartender"}
        </button>
      </form>

      {answer && (
        <div className="p-6 bg-slate-50 border rounded-xl mb-8">
          <h2 className="text-lg font-bold mb-2 text-slate-800">Respuesta de la IA:</h2>
          <p className="text-gray-700 whitespace-pre-wrap">{answer}</p>
        </div>
      )}

      {recommendedCocktails.length > 0 && (
        <div>
          <h2 className="text-xl font-bold mb-4">Cócteles Utilizados para la Recomendación:</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recommendedCocktails.map((c) => (
              <div key={c.slug} className="p-4 border rounded-lg bg-white shadow-sm">
                <h3 className="font-bold text-lg text-slate-900">{c.name}</h3>
                <p className="text-xs text-blue-600 mb-2">{c.category}</p>
                <p className="text-sm text-gray-600">{c.method}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}