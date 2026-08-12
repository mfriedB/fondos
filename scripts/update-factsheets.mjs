#!/usr/bin/env node
/**
 * Actualiza factsheets.json visitando la pagina de cada fondo en
 * fondosbalanz.com y extrayendo el link vigente de "Factsheet en Español".
 *
 * Por que existe este script en vez de resolverlo en el navegador:
 * index.html y patrimonio.html NO pueden hacer fetch() a fondosbalanz.com
 * desde el navegador del usuario, porque ese sitio no manda headers CORS
 * que lo permitan (Access-Control-Allow-Origin). El fetch se ejecuta bien
 * en el servidor -en Node, o en un runner de GitHub Actions- pero el
 * navegador bloquea la respuesta si se intenta desde el cliente.
 *
 * La solucion es este paso intermedio: un script que corre server-side,
 * resuelve los links actuales, y los deja en factsheets.json dentro del
 * propio repositorio. Ese archivo si lo pueden leer las paginas web,
 * porque en ese caso el fetch es al mismo origen (su propio dominio).
 *
 * Uso manual:
 *   node scripts/update-factsheets.mjs
 *
 * Se ejecuta solo, sin intervencion, via GitHub Actions
 * (.github/workflows/update-factsheets.yml).
 */
import { readFile, writeFile } from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const FUND_PAGES_PATH = path.join(DIR, 'fund-pages.json');
const OUTPUT_PATH = path.join(DIR, '..', 'factsheets.json');

// Patron del link tal como aparece en el HTML de fondosbalanz.com:
// <a href="https://cms.balanz.com/PFS/XXXXXX_algo.esp.pdf">Factsheet en Español</a>
const FACTSHEET_RE = /<a[^>]+href="([^"]+)"[^>]*>\s*Factsheet en Espa[ñn]ol\s*<\/a>/i;

async function fetchFactsheetUrl(pageUrl) {
  const res = await fetch(pageUrl, {
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; BalanzFactsheetBot/1.0)' },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const html = await res.text();
  const match = html.match(FACTSHEET_RE);
  if (!match) throw new Error('no se encontro el link "Factsheet en Español" en la pagina');
  return match[1];
}

export async function main() {
  const fundPages = JSON.parse(await readFile(FUND_PAGES_PATH, 'utf8'));
  delete fundPages._comentario;

  let previo = {};
  try {
    previo = JSON.parse(await readFile(OUTPUT_PATH, 'utf8'));
    delete previo._actualizado;
  } catch { /* primera corrida: no hay factsheets.json todavia */ }

  const resultado = {};
  const errores = [];

  for (const [fondo, pageUrl] of Object.entries(fundPages)) {
    try {
      resultado[fondo] = await fetchFactsheetUrl(pageUrl);
      const cambio = previo[fondo] && previo[fondo] !== resultado[fondo] ? ' (cambio)' : '';
      console.log(`OK   ${fondo}: ${resultado[fondo]}${cambio}`);
    } catch (err) {
      // Si falla la visita a un fondo puntual, se conserva el link anterior
      // en vez de dejar ese fondo sin link: un solo fondo caido no debe
      // tirar abajo la actualizacion de los otros 20+.
      errores.push(`${fondo}: ${err.message}`);
      if (previo[fondo]) {
        resultado[fondo] = previo[fondo];
        console.warn(`FALLO ${fondo}: ${err.message} (se mantiene el link anterior)`);
      } else {
        console.warn(`FALLO ${fondo}: ${err.message} (sin link anterior para conservar)`);
      }
    }
  }

  const salida = {
    _actualizado: new Date().toISOString(),
    ...Object.fromEntries(Object.entries(resultado).sort(([a], [b]) => a.localeCompare(b, 'es'))),
  };

  await writeFile(OUTPUT_PATH, JSON.stringify(salida, null, 2) + '\n', 'utf8');

  console.log(`\n${Object.keys(resultado).length} fondos escritos en factsheets.json`);
  if (errores.length) {
    console.log(`${errores.length} con error (ver arriba):`);
    errores.forEach(e => console.log('  - ' + e));
  }
  return { resultado, errores };
}

// Solo se ejecuta solo si se corre como script (node update-factsheets.mjs);
// si se importa desde un test, queda en manos de quien importa llamar a main().
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch(err => {
    console.error('Error fatal:', err);
    process.exit(1);
  });
}

