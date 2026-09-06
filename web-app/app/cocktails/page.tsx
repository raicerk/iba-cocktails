// Este es un Server Component por defecto
async function getCocktails() {
  try {
    // Reemplaza "/cocktails" por el endpoint real de tu API
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/cocktails`, {
      cache: "no-store", // Para que siempre traiga datos frescos
    });
    if (!res.ok) return [];
    return res.json();
  } catch (error) {
    console.error("Error fetching cocktails:", error);
    return [];
  }
}

export default async function CocktailsPage() {
  const cocktails = await getCocktails();

  return (
    <main className="max-w-6xl mx-auto p-6 mt-10">
      <h1 className="text-3xl font-bold mb-8">Catálogo de Cócteles IBA 🍹</h1>
      
      {cocktails.length === 0 ? (
        <p className="text-gray-500">No se encontraron cócteles o la API no está disponible.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cocktails.map((cocktail: any) => (
            <div key={cocktail.id} className="border p-5 rounded-lg shadow-sm hover:shadow-md transition">
              <h2 className="text-xl font-bold text-gray-800">{cocktail.name}</h2>
              <p className="text-sm text-gray-500 mb-4">{cocktail.category}</p>
              <h3 className="font-semibold text-gray-700 text-sm">Ingredientes:</h3>
              <ul className="list-disc list-inside text-sm text-gray-600 mb-4">
                {/* Asumiendo que la API devuelve un array de ingredientes */}
                {cocktail.ingredients?.map((ing: any, index: number) => (
                  <li key={index}>{ing.name || ing}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}