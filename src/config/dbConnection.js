import mongoose from "mongoose";

export const connectDB = async () => {
  try {
    await mongoose.connect(
      "mongodb+srv://pablomainardi33:coderback197@pmcluster.yyam796.mongodb.net/Marchando?retryWrites=true&w=majority"
    );
    console.log("Base de datos conectada");
  } catch (error) {
    console.log(
      `Hubo un error al conectar con la base de datos: ${error.menssage}`
    );
  }
};