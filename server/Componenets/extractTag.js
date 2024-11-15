import { JSDOM } from 'jsdom'; 

export default function extractTag(type, content) {
    const dom = new JSDOM(content);
    const elements = dom.window.document.getElementsByTagName(type);
    return Array.from(elements).map(el => el.innerHTML.trim());
}
