"use strict";

const search = document.querySelector("#termo");
const result = document.querySelector("#resultado");
const empty = document.querySelector("#sem-resultados");

function normalize(text) {
  return text.toLocaleLowerCase("pt-BR").normalize("NFD")
    .replace(/\p{Diacritic}/gu, "").replace(/[^\p{Letter}\p{Number}]+/gu, " ").trim();
}

const sections = Array.from(document.querySelectorAll("main section"), section => ({
  element: section,
  articles: Array.from(section.querySelectorAll("article"), article => ({
    element: article,
    terms: normalize(`${article.textContent} ${article.dataset.keywords || ""}`)
  }))
}));

function filter() {
  const terms = normalize(search.value).split(" ").filter(Boolean);
  let matches = 0;
  for (const section of sections) {
    let sectionMatches = 0;
    for (const article of section.articles) {
      const visible = terms.every(term => article.terms.includes(term));
      article.element.hidden = !visible;
      sectionMatches += Number(visible);
    }
    section.element.hidden = sectionMatches === 0;
    matches += sectionMatches;
  }
  empty.hidden = matches !== 0;
  result.textContent = terms.length === 0 ? "" : matches === 1 ? "1 guia encontrado" : `${matches} guias encontrados`;
}

search.addEventListener("input", filter);
for (const link of document.querySelectorAll("nav a")) {
  link.addEventListener("click", () => {
    search.value = "";
    filter();
  });
}
document.querySelector("#busca").hidden = false;
filter();
