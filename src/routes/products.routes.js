import { Router } from "express";
import { productsService } from "../dao/config.js";

const router = Router();

// Traer todos los productos , con variable para exportar
router.get("/listproducts", async (req, res) => {
  const dataProducts = await productsService.getProducts();
  res.send(dataProducts);
});

// Mostrar todos los productos en la plantilla 'products'
router.get("/", async (req, res) => {
  const dataProducts = await productsService.getProducts();
  res.render("products", { products: dataProducts });
});

// Mostrar el producto segun su id
router.get("/:id", async (req, res) => {
  const id = req.params.id;
  const product = await productsService.getProductById(id);
  res.json({ message: "products", product });
});

// Mostrar el formulario de agregar o actualizar producto en la plantilla 'products'
// Actualizar un producto y redirigir a la vista principal de productos
router.put("/update/:id", async (req, res) => {
  try {
    const { id } = req.params; // Obtén el ID del producto de los parámetros de la solicitud
    const productData = req.body; // Obtén los datos actualizados del producto del cuerpo de la solicitud

    await productsService.updateProduct(id, productData);
    // const dataProducts = await productsService.getProducts();
    // res.render("products", { products: dataProducts });
    // Puedes realizar un manejo adicional aquí si lo necesitas, por ejemplo, enviar una respuesta JSON o redirigir a una nueva página
  } catch (error) {
    console.error("Error al actualizar el producto:", error);
    res.status(500).json({ message: "Error al actualizar el producto" });
  }
});

// Agregar un producto y redirigir a la vista principal de productos
router.post("/add", async (req, res) => {
  const productData = req.body;
  await productsService.addProduct(productData);
  res.redirect("/products");
});

// Eliminar un producto y redirigir a la vista principal de productos
router.post("/delete/:id", async (req, res) => {
  const { id } = req.params;
  await productsService.deleteProduct(id);
  res.redirect("/products");
});

export { router as productsRouter };
