
import ProductsManagerMongo from './mongo/productsManagerMongo.js';
import RecipesManagerMongo from './mongo/recipesManagerMongo.js';

// // Conectar a la base de datos
// connectDB();

// Crear instancias de los gestores de productos y recetas
const productsService = new ProductsManagerMongo();
const recipesService = new RecipesManagerMongo();

export { productsService, recipesService };
