import { recipeModel } from "./models/recipe.model.js";

export default class RecipesManagerMongo {
  constructor() {
    this.model = recipeModel;
  }

  async getRecipeAll() {
    try {
      const recipeAll = await this.model.find().lean();
      return recipeAll;
    } catch (error) {
      console.error("Error al cargar las recetas:", error);
      throw new Error("No se pudo cargar recetas");
    }
  }

  async getRecipeById(i) {
    try {
      const recipeById = await this.model.findById(i).lean();
      return recipeById;
    } catch (error) {
      console.error("Error al cargar la receta:", error);
      throw new Error("No se pudo cargar receta by id ");
    }
  }
  // ... importaciones y configuraciones previas

  //

  async createRecipe(recipeData) {
    try {
      const newRecipe = this.model.create(recipeData);

      return newRecipe;
    } catch (error) {
      console.error("Error al crear la receta:", error);
      throw new Error("No se pudo crear la receta");
    }
  }

  async updateRecipeById(recipeId, updatedData) {
    try {
      const updatedRecipe = await this.model.findByIdAndUpdate(
        recipeId,
        { $set: updatedData },
        { new: true }
      );
      return updatedRecipe;
    } catch (error) {
      console.error("Error al actualizar la receta:", error);
      throw new Error("No se pudo actualizar la receta");
    }
  }

  async deleteRecipeById(recipeId) {
    try {
      const deletedRecipe = await this.model.findByIdAndRemove(recipeId);
      return deletedRecipe;
    } catch (error) {
      console.error("Error al eliminar la receta:", error);
      throw new Error("No se pudo eliminar la receta");
    }
  }
}
