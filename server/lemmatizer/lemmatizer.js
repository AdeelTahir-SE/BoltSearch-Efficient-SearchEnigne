import lemmatizer from "lemmatizer"
export function lemmatizer(word){
    return lemmatizer(word);
}


export function lemmatizerArray(word){
    return word.map(v=>lemmatizer(v));
}



