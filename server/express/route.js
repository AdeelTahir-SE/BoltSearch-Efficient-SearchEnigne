import { Router } from "express";
import fse from "fs-extra";
import { uploadDocument, searchDocuments } from "./childprocess_functions.js"; 
import path from "path";

const router = Router();

router.get("/documents", async (req, res) => {
  try {
    const { words } = req.body;
    const documents = await searchDocuments(words);
    return res.json(documents);
  } catch (error) {
    console.error("Error in GET /documents:", error);
    return res.status(500).json({ error: "Internal Server Error" });
  }
});

// POST Route: Upload Document
router.post("/documents", async (req, res) => {
  try {
    const { file } = req.body; 

    const filePath = path.resolve(__dirname, "../file-upload/uploads");

    await fse.writeJson(path.join(filePath, `${file.name}.json`), file);

    const response = await uploadDocument(path.join(filePath, `${file.name}.json`));

    return res.json({ message: "File uploaded and processed successfully", response });
  } catch (error) {
    console.error("Error in POST /documents:", error);
    return res.status(500).json({ error: "Internal Server Error" });
  }
});

export default router;
