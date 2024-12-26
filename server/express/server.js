import express from "express"
import cors from "cors"
const app=express();
import router from "./route.js"
app.use(express.json())
app.use(cors())
app.use("/api",router)
app.listen(3000,()=>{
    console.log("Server is running on port 3000")
});


