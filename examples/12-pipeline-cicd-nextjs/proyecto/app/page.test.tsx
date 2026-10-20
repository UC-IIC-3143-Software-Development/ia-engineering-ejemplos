import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "vitest";
import Home from "./page";

test("la portada saluda con Hola mundo", () => {
  expect(renderToStaticMarkup(<Home />)).toContain("<h1>Hola mundo</h1>");
});
