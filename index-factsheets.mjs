/* ---------------------------------------------------------------------
   Genera factsheets.json a partir del contenido de la carpeta /WEEKLY

   Este script NO sale a internet ni depende de fondosbalanz.com: solo mira
   los archivos que vos subiste al repositorio y arma un indice con ellos.

   Se espera que los PDF se llamen:

       AAAAMMDD.NombreFondo.esp.pdf

   por ejemplo:  20260731.DolarCortoPlazo.esp.pdf

   De cada archivo saca:
     - la fecha (el prefijo AAAAMMDD)
     - el "slug" del fondo (el nombre del medio, normalizado)

   Si hay varias fechas del mismo fondo (porque subiste el mes nuevo sin
   borrar el viejo) se queda con la MAS RECIENTE, asi que podes acumular
   historico en la carpeta sin romper nada.

   Correr con:  node scripts/index-factsheets.mjs
--------------------------------------------------------------------- */
import { readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const CARPETA = 'WEEKLY';   // ojo: en mayusculas, igual que en el repo
const SALIDA = 'factsheets.json';

// Normaliza a solo letras y numeros en minuscula: "Dolar Corto Plazo" y
// "DolarCortoPlazo" caen los dos en "dolarcortoplazo".
const normalizar = (s) =>
  String(s)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '');

// AAAAMMDD . nombre . esp [.pdf]   -> el .pdf final es opcional porque en la
// carpeta hay archivos que quedaron sin extension.
const PATRON = /^(\d{8})\.(.+?)\.esp(\.pdf)?$/i;

const archivos = await readdir(CARPETA).catch(() => {
  console.error(`No existe la carpeta "${CARPETA}/". Creala y subi ahi los PDF.`);
  process.exit(1);
});

const porSlug = new Map();
const ignorados = [];

for (const archivo of archivos) {
  if (archivo.startsWith('.')) continue;

  const m = archivo.match(PATRON);
  if (!m) {
    ignorados.push(archivo);
    continue;
  }

  const [, fecha, nombre, extension] = m;
  const slug = normalizar(nombre);
  if (!slug) { ignorados.push(archivo); continue; }

  const previo = porSlug.get(slug);
  // Ante dos fechas del mismo fondo, gana la mas nueva
  if (previo && previo.fecha >= fecha) continue;

  porSlug.set(slug, {
    slug,
    nombre,
    fecha,
    url: `${CARPETA}/${encodeURIComponent(archivo)}`,
    esPdf: Boolean(extension),
  });
}

const indice = {
  generado: new Date().toISOString(),
  archivos: [...porSlug.values()].sort((a, b) => a.slug.localeCompare(b.slug)),
};

await writeFile(SALIDA, JSON.stringify(indice, null, 2) + '\n');

console.log(`${indice.archivos.length} factsheets indexados en ${SALIDA}`);

// Avisos utiles, no rompen el build
const sinPdf = indice.archivos.filter((a) => !a.esPdf);
if (sinPdf.length) {
  console.log(
    `\nAviso: ${sinPdf.length} archivo(s) no terminan en .pdf, asi que el navegador ` +
    `los va a descargar en vez de abrirlos. Conviene renombrarlos agregando ".pdf":`
  );
  sinPdf.forEach((a) => console.log(`  - ${path.basename(a.url)}`));
}
if (ignorados.length) {
  console.log(`\nAviso: ${ignorados.length} archivo(s) no siguen el patron AAAAMMDD.Nombre.esp.pdf y quedaron afuera:`);
  ignorados.forEach((a) => console.log(`  - ${a}`));
}
