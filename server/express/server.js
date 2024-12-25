import express from "express"
const app=express();
import router from "./route.js"
app.use(express.json())
app.use("/api",router)
app.listen(3000,()=>{
    console.log("Server is running on port 3000")
});


