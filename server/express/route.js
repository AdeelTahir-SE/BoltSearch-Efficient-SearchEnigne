import { Router } from "express";
import fse from "fs-extra";
import { uploadDocument, searchDocuments } from "./childprocess_functions.js"; 
import path from "path";
import multer from "multer"

const upload = multer({
  storage: multer.diskStorage({
    destination: (req, file, cb) => {
      const uploadPath = path.resolve(__dirname, "../file-upload/uploads");
      fse.ensureDirSync(uploadPath); 
      cb(null, uploadPath);
    },
    filename: (req, file, cb) => {
      cb(null, file.originalname); // Use the original file name
    },
  }),
});

const router = Router();

router.get("/documents", async (req, res) => {
  try {
    const args = req.query.args ? req.query.args.split(",") : [];
    const documents = await searchDocuments(args);
    return res.json(documents);
  } catch (error) {
    console.error("Error in GET /documents:", error);
    return res.status(500).json({ error: "Internal Server Error" });
  }
});

router.post("/documents", upload.single("file"), async (req, res) => {
  
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No file uploaded" });
    }

    const uploadedFilePath = req.file.path;

    const response = await uploadDocument(uploadedFilePath);

    return res.json({
      message: "File uploaded and processed successfully",
      filePath: uploadedFilePath,
      response,
    });
  } catch (error) {
    console.error("Error in POST /documents:", error);
    return res.status(500).json({ error: "Internal Server Error" });
  }
});


export default router;
