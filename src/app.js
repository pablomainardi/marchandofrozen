import express from "express";
import { engine } from "express-handlebars";
import { __dirname } from "./utils.js";
import path from "path";
import { connectDB } from "./config/dbConnection.js"; // Importa el archivo de configuración

const app = express();

// Conexión a la base de datos
connectDB();

// Configuración de Express y middleware
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// Configuración del motor de plantillas (HANDLEBARS)
app.engine("hbs", engine({ extname: ".hbs" }));
app.set("view engine", "hbs");
app.set("views", path.join(__dirname, "/views"));
app.use(express.static("public"));

// Rutas
import { indexRouter } from "./routes/index.routes.js";
import { productsRouter } from "./routes/products.routes.js";
import { recipesRouter } from "./routes/recipes.routes.js";
import { costsRouter } from "./routes/costs.routes.js";

app.use("/", indexRouter);
app.use("/products", productsRouter);
app.use("/recipes", recipesRouter);
app.use("/costs", costsRouter);
//process.env.PORT || y en package json nodemon /src/app.js
// Puerto de escucha
const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`Servidor en funcionamiento en el puerto ${PORT}`);
});
