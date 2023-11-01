
import express from "express";
const router = express.Router();

router.get('/', (req, res) => {
  res.render('index', { title: 'Página de inicio' });
});

export { router as indexRouter };