import express from "express";
import fileUpload from "express-fileupload";
import fse from "fs-extra";
import path from "path";
import cors from"cors";
const app = express();
app.use(cors());
app.use(fileUpload());

const uploadDir = './uploadedfiles';
fse.ensureDirSync(uploadDir);

app.post("/upload", async (req, res) => {
  try {
    if (!req.files || !req.files.file) {
        
      return res.status(400).send("No file was uploaded.");
    }

    const file = req.files.file; 
    const filepath = path.join(uploadDir, file.name); 
    
    const fileContent = file.data.toString(); 
    try {
      const jsonContent = JSON.parse(fileContent);
      await fse.writeJSON(filepath, jsonContent,{spaces: 2});
    } catch (e) {
      await fse.writeFile(filepath, file.data);
    }
   
    res.status(200).json({message:"File uploaded successfully."});
  } catch (err) {
    console.error(err);
    res.status(500).json({error:"Error in saving file."});
  }
});

app.listen(3000, () => console.log("Server is running on port 3000"));
