import { Router } from "express";
import fse from "fs-extra";
import { uploadDocument, searchDocuments } from "./childprocess_functions.js"; 
import path from "path";
import multer from "multer"

const uploadPath = path.resolve('./file-upload/uploads');

const upload = multer({
  storage: multer.diskStorage({
    destination: (req, file, cb) => {
      // Use the absolute path directly
      fse.ensureDirSync(uploadPath); // Ensure the upload directory exists
      cb(null, uploadPath); // Specify the destination folder
    },
    filename: (req, file, cb) => {
      // Use the original file name
      cb(null, file.originalname);
    },
  }),
});
const router = Router();

router.get("/documents", async (req, res) => {
  try {
    console.log("called")
    const args = req.query.args ? req.query.args.split(",") : [];
    const documents = await searchDocuments(args);
    if(!documents){
      return res.status(404).json({ error: "No documents found" });
    } 
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
    console.log(response)
    return res.status(200).json({
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
