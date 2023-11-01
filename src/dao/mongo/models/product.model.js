import mongoose from "mongoose";

const productsCollection = "products";

const productSchema = new mongoose.Schema({
  name: { type: String, required: true },
  brand: String,
  price: { type: Number, required: true },
  unitOfPresentation: {
    type: String,
    enum: ["unidad", "gramos", "mililitros"],
    required: true,
  },
  presentation: { type: Number, required: true },
  unitCostOfPresentation: { type: Number, required: true, default: 0 },
  category: { type: String, required: true },
});

// // Middleware para calcular unitCostOfPresentation
// productSchema.pre("save", function (next) {
//   this.unitCostOfPresentation = this.price / this.presentation;
//   next();
// });

export const productModel = mongoose.model(productsCollection, productSchema);
