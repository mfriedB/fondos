// Actualiza benchmarks.json: las series de referencia que la calculadora
// puede sumar a los graficos de rendimiento (inflacion, dolar oficial y dolar MEP).
//
// Fuentes:
//   - Inflacion: INDEC, IPC Nivel General Nacional (base dic 2016), publicado
//     por la API de Series de Tiempo del Estado nacional (datos.gob.ar).
//     Se cruza contra la "Inflacion mensual" que publica el BCRA.
//   - Dolar oficial: BCRA, tipo de cambio mayorista de referencia
//     (Comunicacion A 3500), por la API de estadisticas del BCRA.
//   - Dolar MEP: API de ArgentinaDatos (cotizacion "bolsa", precio de venta).
//     No es una fuente oficial: no existe una serie oficial publica del MEP.
//
// Si una fuente falla o devuelve algo raro, se conserva lo que ya habia en
// benchmarks.json para esa serie: nunca se pisa un dato bueno con uno malo.
//
// Uso: node scripts/actualizar-benchmarks.mjs [--probar]

import { readFile, writeFile } from 'node:fs/promises';

const ARCHIVO = 'benchmarks.json';
const PROBAR = process.argv.includes('--probar');
const DESDE = '2019-01-01';     // historia que se guarda

const SERIE_IPC = '148.3_INIVELNAL_DICI_M_26';
const URL_IPC = `https://apis.datos.gob.ar/series/api/series/?ids=${SERIE_IPC}&start_date=${DESDE}&limit=5000&format=json`;
const URL_BCRA_INFLACION = 'https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/27?limit=1000';
const BCRA_VARIABLES = 'https://api.bcra.gob.ar/estadisticas/v4.0/monetarias';
const BCRA_ID_MAYORISTA = 5;    // Tipo de cambio mayorista de referencia (Com. A 3500)
const URL_MEP = 'https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa';

async function traerJson(url, opciones = {}){
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 30000);
  try{
    const r = await fetch(url, { ...opciones, signal: ctrl.signal, headers: { accept: 'application/json', 'user-agent': 'calculadora-fondos/benchmarks', ...(opciones.headers || {}) } });
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } finally { clearTimeout(t); }
}

// ---- Inflacion: indice IPC del INDEC, un valor por mes
async function inflacionIndec(){
  const j = await traerJson(URL_IPC);
  const datos = (j.data || [])
    .filter(f => f && f[0] && Number.isFinite(Number(f[1])) && Number(f[1]) > 0)
    .map(f => [String(f[0]).slice(0, 7), Number(Number(f[1]).toFixed(4))]);
  if(datos.length < 24) throw new Error(`IPC: solo ${datos.length} meses`);
  for(let i = 1; i < datos.length; i++){
    const v = datos[i][1] / datos[i - 1][1] - 1;
    if(!(v > -0.05 && v < 0.40)) throw new Error(`IPC: variacion fuera de rango en ${datos[i][0]} (${(v * 100).toFixed(1)}%)`);
  }
  return datos;
}

// Cruce: la variacion mensual que da el indice del INDEC contra la que publica el BCRA
async function cruceBcra(datos){
  try{
    const j = await traerJson(URL_BCRA_INFLACION);
    const det = (j.results && j.results[0] && j.results[0].detalle) || [];
    const bcra = new Map(det.map(d => [String(d.fecha).slice(0, 7), Number(d.valor)]));
    const difs = [];
    for(let i = Math.max(1, datos.length - 12); i < datos.length; i++){
      const b = bcra.get(datos[i][0]);
      if(b == null) continue;
      const v = (datos[i][1] / datos[i - 1][1] - 1) * 100;
      difs.push([datos[i][0], +v.toFixed(2), b, +(v - b).toFixed(2)]);
    }
    const mal = difs.filter(d => Math.abs(d[3]) > 0.15);
    console.log(`Cruce INDEC vs BCRA (ultimos ${difs.length} meses):`, mal.length ? `DIFERENCIAS ${JSON.stringify(mal)}` : 'coinciden');
    return { meses: difs.length, coincide: mal.length === 0 };
  } catch(e){
    console.log('Cruce con BCRA no disponible:', e.message);
    return null;
  }
}

// Controla que una serie diaria tenga historia suficiente y no tenga saltos imposibles
function validarDiaria(nombre, datos){
  if(datos.length < 100) throw new Error(`${nombre}: solo ${datos.length} ruedas`);
  for(let i = 1; i < datos.length; i++){
    const v = datos[i][1] / datos[i - 1][1] - 1;
    if(!(v > -0.30 && v < 1.30)) throw new Error(`${nombre}: salto fuera de rango el ${datos[i][0]} (${(v * 100).toFixed(1)}%)`);
  }
  const atraso = (Date.now() - new Date(datos.at(-1)[0] + 'T00:00:00Z').getTime()) / 86400000;
  if(atraso > 12) throw new Error(`${nombre}: el ultimo dato es del ${datos.at(-1)[0]}`);
  return datos;
}

// ---- Dolar oficial: BCRA, tipo de cambio mayorista de referencia (Com. A 3500)
async function oficialBcra(){
  // Se confirma que el identificador siga correspondiendo a la serie mayorista
  const lista = await traerJson(`${BCRA_VARIABLES}?limit=1000`);
  const variable = (lista.results || []).find(v => v.idVariable === BCRA_ID_MAYORISTA);
  const descripcion = variable ? String(variable.descripcion || '') : '';
  if(!/mayorista/i.test(descripcion)) throw new Error(`BCRA: la variable ${BCRA_ID_MAYORISTA} no es el tipo de cambio mayorista ("${descripcion}")`);
  const hoy = new Date().toISOString().slice(0, 10);
  const porFecha = new Map();
  for(let offset = 0; offset < 20000; offset += 1000){
    const j = await traerJson(`${BCRA_VARIABLES}/${BCRA_ID_MAYORISTA}?desde=${DESDE}&hasta=${hoy}&limit=1000&offset=${offset}`);
    const det = (j.results && j.results[0] && j.results[0].detalle) || [];
    det.forEach(d => {
      const v = Number(d.valor);
      if(d.fecha && Number.isFinite(v) && v > 0) porFecha.set(String(d.fecha).slice(0, 10), Number(v.toFixed(4)));
    });
    if(det.length < 1000) break;
  }
  const datos = [...porFecha.entries()].sort((a, b) => a[0] < b[0] ? -1 : 1);
  return { datos: validarDiaria('Dolar oficial BCRA', datos), descripcion };
}

// ---- Dolar MEP: ArgentinaDatos, cotizacion "bolsa" (precio de venta de cada dia)
async function mepArgentinaDatos(){
  const j = await traerJson(URL_MEP);
  const porFecha = new Map();
  (Array.isArray(j) ? j : []).forEach(f => {
    const v = Number(f && f.venta);
    if(f && f.fecha && Number.isFinite(v) && v > 0) porFecha.set(String(f.fecha).slice(0, 10), Number(v.toFixed(2)));
  });
  const datos = [...porFecha.entries()].filter(f => f[0] >= DESDE).sort((a, b) => a[0] < b[0] ? -1 : 1);
  return validarDiaria('Dolar MEP', datos);
}

// ---- Solo para probar conectividad desde el runner (no escribe nada)
async function probar(){
  const pruebas = {
    'datos.gob.ar (INDEC IPC)': () => inflacionIndec().then(d => `${d.length} meses, ultimo ${d.at(-1)}`),
    'BCRA inflacion mensual': () => traerJson(URL_BCRA_INFLACION).then(j => JSON.stringify(j.results[0].detalle.slice(0, 2))),
    'BCRA dolar mayorista A 3500': () => oficialBcra().then(r => `"${r.descripcion}": ${r.datos.length} ruedas, ${r.datos[0]} a ${r.datos.at(-1)}`),
    'ArgentinaDatos dolar MEP': () => mepArgentinaDatos().then(d => `${d.length} ruedas, ${d[0]} a ${d.at(-1)}`),
  };
  for(const [nombre, f] of Object.entries(pruebas)){
    try{ console.log(`OK   ${nombre}: ${await f()}`); }
    catch(e){ console.log(`FALLA ${nombre}: ${e.message} ${e.cause ? '(' + (e.cause.code || e.cause.message) + ')' : ''}`); }
  }
}

async function main(){
  if(PROBAR) return probar();
  let previo = {};
  try{ previo = JSON.parse(await readFile(ARCHIVO, 'utf8')); } catch(e){ /* primera vez */ }
  const SERIES = ['inflacion', 'oficial', 'mep'];
  const salida = {};
  SERIES.forEach(k => { salida[k] = previo[k] || null; });
  let fallas = 0;

  try{
    const datos = await inflacionIndec();
    const cruce = await cruceBcra(datos);
    salida.inflacion = {
      fuente: 'INDEC, IPC Nivel General Nacional (base dic 2016)',
      via: 'API de Series de Tiempo de datos.gob.ar',
      serie: SERIE_IPC,
      cruceBcra: cruce,
      datos,
    };
    console.log(`Inflacion: ${datos.length} meses, ultimo ${datos.at(-1)[0]}`);
  } catch(e){ fallas++; console.log('::warning::Inflacion sin actualizar:', e.message); }

  try{
    const r = await oficialBcra();
    salida.oficial = { fuente: 'BCRA, tipo de cambio mayorista de referencia (Com. A 3500)', via: 'API de estadísticas del BCRA', serie: r.descripcion, datos: r.datos };
    console.log(`Dolar oficial: ${r.datos.length} ruedas, ultima ${r.datos.at(-1)[0]}`);
  } catch(e){ fallas++; console.log('::warning::Dolar oficial sin actualizar:', e.message); }

  try{
    const datos = await mepArgentinaDatos();
    salida.mep = { fuente: 'ArgentinaDatos, dólar MEP (precio de venta)', via: 'API de ArgentinaDatos', oficial: false, datos };
    console.log(`Dolar MEP: ${datos.length} ruedas, ultima ${datos.at(-1)[0]}`);
  } catch(e){ fallas++; console.log('::warning::Dolar MEP sin actualizar:', e.message); }

  const cuerpo = JSON.stringify(SERIES.map(k => salida[k]));
  const cuerpoPrevio = JSON.stringify(SERIES.map(k => previo[k] || null));
  if(cuerpo === cuerpoPrevio){ console.log('Sin cambios en los datos.'); return; }
  const out = { actualizado: new Date().toISOString(), ...salida };
  await writeFile(ARCHIVO, JSON.stringify(out) + '\n');
  console.log(`${ARCHIVO} actualizado (${fallas} fuente(s) con falla).`);
}

main().catch(e => { console.error(e); process.exit(1); });
