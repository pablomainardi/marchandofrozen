console.log("Vista PRoducts");

const formContainer = document.getElementById("formContainer");

document.addEventListener("DOMContentLoaded", () => {
  const deleteButtons = document.querySelectorAll(".delete-btn");

  deleteButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const productId = button.getAttribute("value");
      deleteProduct(productId);
    });
  });
});

const addBtn = document.querySelector(".action-button");

addBtn.addEventListener("click", () => showAddForm());

function showAddForm() {
  const addButton = document.querySelector(".action-button");
  if (addButton.textContent === "Producto Nuevo") {
    formContainer.innerHTML = `
      <form id="addProductForm" action="/products/add" method="POST">
        <label for="name">Nombre del Producto:</label>
        <input type="text" id="name" name="name" placeholder="Nombre del Producto" required>
        <label for="brand">Marca:</label>
        <input type="text" id="brand" name="brand" placeholder="Marca del Producto">
        <label for="price">Precio:</label>
        <input type="number" id="price" name="price" placeholder="Precio del Producto" required>
        <label for="presentation">Presentación:</label>
        <input type="number" id="presentation" name="presentation" placeholder="Presentación" required>
        <label for="unitOfPresentation">Unidad de Presentación:</label>
        <select id="unitOfPresentation" name="unitOfPresentation" required>
          <option value="gramos">Gramos</option>
          <option value="mililitros">Mililitros</option>
          <option value="unidad">Unidad</option>
        </select>
        <label for="category">Categoría:</label>
        <input type="text" id="category" name="category" placeholder="Categoría del Producto" required>
        <button class="action-button" type="submit">Agregar Producto</button>
      </form>
    `;
    addButton.style.display = "none"; // Esta línea oculta el botón "Producto Nuevo"
  } else {
    formContainer.innerHTML = `
    <form id="addProductForm" action="/products/add" method="POST">
    <label for="name">Nombre del Producto:</label>
    <input type="text" id="name" name="name" placeholder="Nombre del Producto" required>
    <label for="brand">Marca:</label>
    <input type="text" id="brand" name="brand" placeholder="Marca del Producto">
    <label for="price">Precio:</label>
    <input type="number" id="price" name="price" placeholder="Precio del Producto" required>
    <label for="presentation">Presentación:</label>
    <input type="number" id="presentation" name="presentation" placeholder="Presentación" required>
    <label for="unitOfPresentation">Unidad de Presentación:</label>
    <select id="unitOfPresentation" name="unitOfPresentation" required>
      <option value="gramos">Gramos</option>
      <option value="mililitros">Mililitros</option>
      <option value="unidad">Unidad</option>
    </select>
    <label for="category">Categoría:</label>
    <input type="text" id="category" name="category" placeholder="Categoría del Producto" required>
    <button class="action-button" type="submit">Agregar Producto</button>
  </form>
  
    `;
  }
  const productNameInput = document.getElementById("name");
  productNameInput.focus();
}

function enableProductFields(productId) {
  const productItem = document.getElementById(productId);
  const productInfo = productItem.querySelector(".product-info");
  const inputFields = productInfo.querySelectorAll("input, select");

  inputFields.forEach((input) => {
    input.removeAttribute("disabled");
  });

  const editButton = productItem.querySelector(".edit-btn");
  editButton.textContent = "Actualizar";
  editButton.removeEventListener("click", enableProductFields);
  editButton.addEventListener("click", () => {
    updateProduct(productId, getInputData(productItem));
  });
}

function updateProduct(productId, updatedData) {
  const productItem = document.getElementById(productId);
  const productInfo = productItem.querySelector(".product-info");
  const inputFields = productInfo.querySelectorAll("input, select");

  // Lógica para llamar a la función de actualización del producto con los datos actualizados y el ID del producto
  updateProductData(productId, updatedData);
  console.log("productId", productId);
  console.log("updatedData", updatedData);

  inputFields.forEach((input) => {
    input.setAttribute("disabled", true);
  });

  const editButton = productItem.querySelector(".edit-btn");
  editButton.textContent = "Editar";
  editButton.removeEventListener("click", updateProduct);
  editButton.addEventListener("click", () => {
    enableProductFields(productId);
  });
}

async function deleteProduct(productId) {
  try {
    const isConfirmed = confirm(
      "¿Estás seguro de que deseas eliminar este producto?"
    );
    if (isConfirmed) {
      await fetch(`/products/delete/${productId}`, { method: "POST" });
    }
    location.reload();
  } catch (error) {
    console.error("Error al eliminar el producto:", error);
  }
}

function getInputData(productItem) {
  const productInfo = productItem.querySelector(".product-info");
  const inputFields = productInfo.querySelectorAll("input, select");
  const updatedData = {};
  inputFields.forEach((input) => {
    if (input.type === "number") {
      updatedData[input.name] = parseFloat(input.value);
    } else {
      updatedData[input.name] = input.value;
    }
  });
  console.log("updateData", updatedData);
  return updatedData;
}

async function updateProductData(productId, updatedData) {
  try {
    const response = await fetch(`/products/update/${productId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(updatedData), // Convierte los datos a formato JSON
    });
    if (!response.ok) {
      throw new Error("Error al actualizar el producto");
    }
    const responseData = await response.json();
    console.log("Producto actualizado:", responseData);
  } catch (error) {
    console.error("Error al actualizar el producto:", error);
  }
}
