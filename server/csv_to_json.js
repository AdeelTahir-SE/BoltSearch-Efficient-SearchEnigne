import csv from "csvtojson";
import { createReadStream, createWriteStream } from "fs";

const inputFilePath = "E:/codingfolder/datasetboltsearch/Questions.csv"; // Input CSV file path
const outputFilePath = "./server/jsondataset/Questions.json"; // Output JSON file path

const processCsvStream = async () => {
  try {
    const readStream = createReadStream(inputFilePath);

    const writeStream = createWriteStream(outputFilePath);

    writeStream.write("[\n"); 

    let firstLine = true;

    readStream
      .pipe(csv())
      .on("data", (data) => {
        const jsonObject = JSON.parse(data.toString());
        const formattedJson = JSON.stringify(jsonObject, null, 2); 

        if (!firstLine) {
          writeStream.write(",\n");
        }
        writeStream.write(formattedJson);
        firstLine = false;
      })
      .on("end", () => {
        writeStream.write("\n]");
        console.log(`JSON data successfully written to ${outputFilePath}`);
      })
      .on("error", (err) => {
        console.error("Error processing CSV:", err);
      });
  } catch (err) {
    console.error("Error in stream processing:", err);
  }
};

processCsvStream();
