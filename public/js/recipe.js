let listaIngredientes = [];

const buscarProducto = async (nombre) => {
  try {
    const response = await fetch("http://localhost:8080/products/listproducts");
    if (!response.ok) {
      throw new Error("Error al obtener la lista de productos");
    }
    const data = await response.json();
    const prodBusted = data.filter((producto) =>
      producto.name.includes(nombre)
    );

    return prodBusted;
  } catch (error) {
    console.error("Error al obtener la lista de productos:", error);
  }
};

const crearRecetaBtn = document.getElementById("crear-receta-btn");
const crearRecetaContainer = document.getElementById("crear-receta-container");

const showCrearRecetaContainer = () => {
  crearRecetaContainer.style.display = "block";
};
crearRecetaBtn.addEventListener("click", showCrearRecetaContainer);

const ingredientesContainer = document.getElementById("ingredientes-container");
const agregarIngredientes = (producto) => {
  const divIngredientes = document.createElement("div");
  divIngredientes.classList.add("ingredientes");

  const nombreProductoLabel = document.createElement("label");
  nombreProductoLabel.textContent = "Nombre del Producto:";
  const nombreProductoInput = document.createElement("input");
  nombreProductoInput.value = producto.name;
  nombreProductoInput.disabled = true;
  nombreProductoInput.name = "nombre-producto";
  nombreProductoInput.classList.add("inputName"); // Agregando el nombre

  const costUnitPresentationLabel = document.createElement("label");
  costUnitPresentationLabel.textContent = "Costo por Unidad de Presentación:";
  const costUnitPresentationInput = document.createElement("input");
  costUnitPresentationInput.value = parseFloat(
    Math.round(producto.unitCostOfPresentation * 100) / 100
  ).toFixed(2);
  costUnitPresentationInput.disabled = true;
  costUnitPresentationInput.name = "costo-unidad-producto"; // Agregando el nombre

  const unitOfPresentationLabel = document.createElement("label");
  unitOfPresentationLabel.textContent = "Unidad de calculo";
  const unitOfPresentationInput = document.createElement("input");
  unitOfPresentationInput.value = producto.unitOfPresentation;
  unitOfPresentationInput.disabled = true;

  const cantidadNecesariaLabel = document.createElement("label");
  cantidadNecesariaLabel.textContent = "Cantidad Necesaria:";
  const cantidadNecesariaInput = document.createElement("input");
  cantidadNecesariaInput.type = "number";
  cantidadNecesariaInput.name = "cantidad-necesaria"; // Agregando el nombre

  const costoTotalLabel = document.createElement("label");
  costoTotalLabel.textContent = "Costo Total del Producto:";
  const costoTotalInput = document.createElement("input");
  costoTotalInput.disabled = true;
  costoTotalInput.name = "costo-total-producto"; // Agregando el nombre

  cantidadNecesariaInput.addEventListener("input", () => {
    const cantidadNecesariaValue = cantidadNecesariaInput.value;
    const unitCostOfPresentationValue = producto.unitCostOfPresentation;
    const calculatedCost = cantidadNecesariaValue * unitCostOfPresentationValue;
    costoTotalInput.value = calculatedCost;
  });

  // Resto del código para agregar los elementos de cada ingrediente
  divIngredientes.appendChild(nombreProductoLabel);
  divIngredientes.appendChild(nombreProductoInput);
  divIngredientes.appendChild(costUnitPresentationLabel);
  divIngredientes.appendChild(costUnitPresentationInput);
  divIngredientes.appendChild(unitOfPresentationLabel);
  divIngredientes.appendChild(unitOfPresentationInput);
  divIngredientes.appendChild(cantidadNecesariaLabel);
  divIngredientes.appendChild(cantidadNecesariaInput);
  divIngredientes.appendChild(costoTotalLabel);
  divIngredientes.appendChild(costoTotalInput);

  const eliminarBoton = document.createElement("button");
  eliminarBoton.textContent = "Eliminar";
  eliminarBoton.addEventListener("click", () => {
    divIngredientes.remove();
    const index = listaIngredientes.findIndex(
      (item) => item.nombre === producto.name
    );
    if (index !== -1) {
      listaIngredientes.splice(index, 1);
    }
    listaIngredientesHandler();
  });

  divIngredientes.appendChild(eliminarBoton);

  ingredientesContainer.appendChild(divIngredientes);
};

///

const buscarProductoInput = document.getElementById("nombre-producto-input");

const buscarProductoFunc = async () => {
  const nombreProducto = buscarProductoInput.value;
  const producto = await buscarProducto(nombreProducto);
  if (producto.length > 0) {
    agregarIngredientes(producto[0]);
  }
};

buscarProductoInput.addEventListener("keypress", async (event) => {
  if (event.key === "Enter") {
    buscarProductoInput.focus();
    await buscarProductoFunc();
  }
});

///

const agregarReceta = async () => {
  try {
    let sumCostsTotal = 0; // Inicializa la suma de costos totales

    const nameRecipe = document.getElementById("nombre-receta").value;
    const ingredients = document.querySelectorAll(".ingredientes");
    listaIngredientes = [];
    ingredients.forEach((element) => {
      const nombre = element.querySelector(
        'input[name="nombre-producto"]'
      ).value;

      const costUnitPresentation = element.querySelector(
        'input[name="costo-unidad-producto"]'
      ).value;

      const cantidadNecesaria = element.querySelector(
        'input[name="cantidad-necesaria"]'
      ).value;

      const costoTotal = element.querySelector(
        'input[name="costo-total-producto"]'
      ).value;

      // Agregar cada ingrediente a la lista deingredients
      listaIngredientes.push({
        nameProduct: nombre,
        unitCostOfPresentation: costUnitPresentation,
        quantityNeeded: cantidadNecesaria,
        costOfProduct: costoTotal,
      });

      // Sumar los costos totales
      sumCostsTotal += Number(costoTotal);
    });

    const data = {
      nameRecipe,
      ingredients: listaIngredientes,
      costsTotalRecipe: parseFloat(
        Math.round(sumCostsTotal * 100) / 100
      ).toFixed(2), // Agrega la suma de los costos totales al objeto de datos
    };

    console.log(data);

    // Mostrar el resultado en el elemento "costsTotalRecipe"
    const costsTotalRecipeElement = document.getElementById("costsTotalRecipe");
    costsTotalRecipeElement.innerText = parseFloat(
      Math.round(sumCostsTotal * 100) / 100
    ).toFixed(2);

    // Restablecer los valores de los ingredientes
    const ingredientes = document.querySelectorAll(".ingredientes");
    ingredientes.forEach((element) => {
      element.querySelector('input[name="cantidad-necesaria"]').value = "";
      element.querySelector('input[name="costo-total-producto"]').value = "";
    });

    // Ocultar el contenedor de agregar receta
    crearRecetaContainer.style.display = "none";

    Swal.fire({
      position: "top",
      icon: "success",
      title: "Se ha agregado la receta",
      showConfirmButton: false,
      timer: 1500,
    });

    const response = await fetch("/recipes/add", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error("Error al agregar la receta");
    }
  } catch (error) {
    console.error("Error al agregar la receta:", error);
    // Manejo de errores si la receta no se puede agregar.
  }
};

// Lógica adicional si la receta se agrega con éxito

const buscarProductoBtn = document.getElementById("buscar-producto-btn");

const agregarRecetaBtn = document.getElementById("agregar-receta-btn");

buscarProductoBtn.addEventListener("click", async () => {
  buscarProductoInput.focus();
  const nombreProducto = document.getElementById("nombre-producto-input").value;
  const producto = await buscarProducto(nombreProducto);
  if (producto.length > 0) {
    agregarIngredientes(producto[0]);
  }
});

agregarRecetaBtn.addEventListener("click", agregarReceta);

// PARA ELIMINAR RECETA

const eliminarReceta = async (id) => {
  try {
    const confirmacion = await Swal.fire({
      title: "¿Estás seguro?",
      text: "No podrás revertir esto",
      icon: "warning",
      showCancelButton: true,
      confirmButtonColor: "#3085d6",
      cancelButtonColor: "#d33",
      confirmButtonText: "Sí, eliminarlo!",
    });

    if (confirmacion.isConfirmed) {
      const response = await fetch(`/recipes/delete/${id}`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error("Error al eliminar la receta");
      }

      const data = await response.json();
      console.log(data);

      Swal.fire("Eliminado!", "La receta ha sido eliminada.", "success");
    }
  } catch (error) {
    console.error("Error al eliminar la receta:", error);
  }
};

// Resto del código ...

const renderRecipes = (recipes) => {
  const divPrueba = document.getElementById("divprueba");
  divPrueba.innerHTML = "";

  recipes.forEach((recipe) => {
    const recipeCard = document.createElement("div");
    recipeCard.classList.add("recipe-card");

    const recipeName = document.createElement("div");
    recipeName.innerHTML = `<h3><strong>Nombre de la Receta:</strong> ${recipe.nameRecipe}</h3>`;

    const ingredientsList = document.createElement("div");
    recipe.ingredients.forEach((ingredient) => {
      const ingredientCard = document.createElement("div");
      ingredientCard.classList.add("ingredient-card");

      // ... (Código para mostrar los detalles del ingrediente)

      ingredientsList.appendChild(ingredientCard);
    });

    const totalCost = document.createElement("p");
    totalCost.innerHTML = `<strong>Costo Total de la Receta:</strong> ${recipe.costsTotalRecipe}`;

    const eliminarButton = document.createElement("button");
    eliminarButton.textContent = "Eliminar Receta";
    eliminarButton.addEventListener("click", () => {
      eliminarReceta(recipe._id);
    });

    recipeCard.appendChild(recipeName);
    recipeCard.appendChild(ingredientsList);
    recipeCard.appendChild(totalCost);
    recipeCard.appendChild(eliminarButton);

    divPrueba.appendChild(recipeCard);
  });
};

// ACTUALIZAR RECETA
// Resto del código...

const updateRecipeBtns = document.querySelectorAll(".update-recipe-btn");

updateRecipeBtns.forEach((btn) => {
  btn.addEventListener("click", async (event) => {
    const recipeId = event.target.dataset.id; // Obtener el ID de la receta

    // Redirigir a la página de actualización de productos con el ID de la receta
    window.location.href = `/recipes/update/${recipeId}`;
  });
});

// Resto del código...
