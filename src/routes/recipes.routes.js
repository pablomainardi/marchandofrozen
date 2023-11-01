import { Router } from "express";
import { recipesService } from "../dao/config.js";

const router = Router();

router.get("/", async (req, res) => {
  try {
    const recipes = await recipesService.getRecipeAll();
    res.render("recipes", { recipes });
  } catch (error) {
    console.error("Error al cargar las recetas:", error);
    res.status(500).json({ error: "No se pudo cargar las recetas" });
  }
});

router.post("/add", async (req, res) => {
  try {
    const recipeData = req.body;
    console.log("add", recipeData);
    await recipesService.createRecipe(recipeData);
  } catch (error) {
    console.error("Error al crear la receta:", error);
    res.status(500).json({ error: "No se pudo crear la receta" });
  }
});

router.get("/update/:id", async (req, res) => {
  try {
    const recipeId = req.params.id;
    const recipe = await recipesService.getRecipeById(recipeId);
    console.log(recipe);
    res.render("updateRecipe", { recipe });
  } catch (error) {
    console.error("Error al cargar la receta:", error);
    res.status(500).json({ error: "No se pudo cargar la receta" });
  }
});

router.put("/update/:id", async (req, res) => {
  try {
    const recipeId = req.params.id;
    const updatedData = req.body;
    const updatedRecipe = await recipesService.updateRecipeById(
      recipeId,
      updatedData
    );
    res
      .status(200)
      .json({ message: "Receta actualizada", recipe: updatedRecipe });
  } catch (error) {
    console.error("Error al actualizar la receta:", error);
    res.status(500).json({ error: "No se pudo actualizar la receta" });
  }
});

router.delete("/delete/:id", async (req, res) => {
  try {
    const recipeId = req.params.id;
    const deletedRecipe = await recipesService.deleteRecipeById(recipeId);
    res
      .status(200)
      .json({ message: "Receta eliminada", recipe: deletedRecipe });
  } catch (error) {
    console.error("Error al eliminar la receta:", error);
    res.status(500).json({ error: "No se pudo eliminar la receta" });
  }
});

export { router as recipesRouter };
