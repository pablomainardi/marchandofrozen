import mongoose from "mongoose";

const { Schema } = mongoose;

const recipeCollection = "recipes";
const recipeSchema = new Schema({
  nameRecipe: { type: String, required: true },
  ingredients: [
    {
      nameProduct: { type: String, required: true },
      unitCostOfPresentation: { type: Number, required: true },
      quantityNeeded: { type: Number, required: true },
      costOfProduct: { type: Number, required: true },
    },
  ],
  costsTotalRecipe: { type: Number, required: true },
});

export const recipeModel = mongoose.model(recipeCollection, recipeSchema);
