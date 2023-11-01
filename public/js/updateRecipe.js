console.log("VISTA UPDATE RECIPES");
const updateRecipeForm = document.getElementById("update-recipe-form");

updateRecipeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const recipeId = document.getElementById("id_recipe_sel").value; // Obtener el ID de la receta
  const updatedRecipeData = {
    nameRecipe: document.getElementById("nombre-receta").value,
    ingredients: Array.from(document.querySelectorAll(".ingredient")).map(
      (ingredient) => {
        return {
          nameProduct: ingredient.querySelector('input[name="nombre-producto"]')
            .value,
          unitCostOfPresentation: parseFloat(
            ingredient.querySelector('input[name="costo-unidad-producto"]')
              .value
          ),
          quantityNeeded: parseFloat(
            ingredient.querySelector('input[name="cantidad-necesaria"]').value
          ),
          costOfProduct: parseFloat(
            ingredient.querySelector('input[name="costo-total-producto"]').value
          ),
        };
      }
    ),
    costsTotalRecipe: parseFloat(
      document.getElementById("costsTotalRecipe").value
    ),
  };

  try {
    const response = await fetch(`/recipes/update/${recipeId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(updatedRecipeData),
    });

    if (!response.ok) {
      throw new Error("Error al enviar los datos actualizados");
    }
    Swal.fire({
      position: "top",
      icon: "success",
      title: "Receta actualizada",
      showConfirmButton: false,
      timer: 1500,
    });

    const data = await response.json();
    console.log(data);
    // Acciones adicionales después de actualizar los datos

    // Realizar acciones adicionales después de la actualización exitosa
  } catch (error) {
    console.error("Error al enviar los datos actualizados:", error);
    // Acciones adicionales en caso de error

    Swal.fire({
      icon: "error",
      title: "Error",
      text: "Error al enviar los datos actualizados",
    });
  }
});
