"use client";

import { useState, useEffect } from "react";
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

export default function CatalogPage() {
  const [cocktails, setCocktails] = useState<Cocktail[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);

  // Estados de filtros
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedIngredient, setSelectedIngredient] = useState("");

  const API_URL = process.env.NEXT_PUBLIC_API_URL;

  // Carga o filtrado de cócteles
  const fetchCocktails = async () => {
    setLoading(true);
    try {
      let endpoint = `${API_URL}`;

      if (searchQuery.trim()) {
        endpoint = `${API_URL}/search?q=${encodeURIComponent(searchQuery)}`;
      } else if (selectedCategory) {
        endpoint = `${API_URL}/category/${encodeURIComponent(selectedCategory)}`;
      } else if (selectedIngredient.trim()) {
        endpoint = `${API_URL}/ingredient/${encodeURIComponent(selectedIngredient)}`;
      }

      const res = await fetch(endpoint);
      const data = await res.json();
      setCocktails(data.cocktails || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error("Error al consultar la API:", err);
      setCocktails([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCocktails();
  }, [selectedCategory]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchCocktails();
  };

  const clearFilters = () => {
    setSearchQuery("");
    setSelectedCategory("");
    setSelectedIngredient("");
    setTimeout(fetchCocktails, 50);
  };

  return (
    <main className="max-w-6xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6 text-slate-800">Catálogo de Cócteles IBA 🍸</h1>

      {/* Controles de Filtrado */}
      <div className="bg-slate-50 p-4 rounded-xl border mb-8 flex flex-col md:flex-row gap-4 items-center">
        {/* Búsqueda por Nombre */}
        <form onSubmit={handleSearchSubmit} className="flex-1 flex gap-2 w-full">
          <input
            type="text"
            placeholder="Buscar por nombre (ej: Mojito)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="p-2 border rounded-md flex-1 text-black"
          />
          <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
            Buscar
          </button>
        </form>

        {/* Filtro por Categoría */}
        <select
          value={selectedCategory}
          onChange={(e) => {
            setSearchQuery("");
            setSelectedIngredient("");
            setSelectedCategory(e.target.value);
          }}
          className="p-2 border rounded-md text-black w-full md:w-auto"
        >
          <option value="">Todas las Categorías</option>
          <option value="The Unforgettables">The Unforgettables</option>
          <option value="Contemporary Classics">Contemporary Classics</option>
          <option value="New Era Drinks">New Era Drinks</option>
        </select>

        {/* Filtro por Ingrediente */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setSearchQuery("");
            setSelectedCategory("");
            fetchCocktails();
          }}
          className="flex gap-2 w-full md:w-auto"
        >
          <input
            type="text"
            placeholder="Ingrediente (ej: Gin)..."
            value={selectedIngredient}
            onChange={(e) => setSelectedIngredient(e.target.value)}
            className="p-2 border rounded-md text-black w-full"
          />
          <button type="submit" className="bg-slate-800 text-white px-3 py-2 rounded-md hover:bg-slate-900">
            Filtrar
          </button>
        </form>

        <button onClick={clearFilters} className="text-sm text-red-600 underline whitespace-nowrap">
          Limpiar
        </button>
      </div>

      {/* Contador de resultados */}
      <p className="text-gray-500 mb-4">Total encontrados: {total}</p>

      {/* Grid de Cócteles */}
      {loading ? (
        <p className="text-center text-gray-500">Cargando cócteles...</p>
      ) : cocktails.length === 0 ? (
        <p className="text-center text-gray-500">No se encontraron cócteles.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {cocktails.map((c) => (
            <div key={c.slug} className="border rounded-xl overflow-hidden shadow-sm hover:shadow-md transition">
              {c.image_url && (
                <img src={c.image_url} alt={c.name} className="w-full h-48 object-cover" />
              )}
              <div className="p-4">
                <span className="text-xs font-bold text-blue-600 uppercase">{c.category}</span>
                <h2 className="text-xl font-bold text-gray-900 mt-1">{c.name}</h2>
                <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                  Ingredientes: {c.ingredients.map((i) => i.ingredient).join(", ")}
                </p>
                <Link
                  href={`/cocktails/${c.slug}`}
                  className="inline-block mt-4 text-blue-600 font-semibold hover:underline"
                >
                  Ver Receta Completa →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}