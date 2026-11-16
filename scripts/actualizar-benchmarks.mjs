// Actualiza benchmarks.json: las series de referencia que la calculadora
// puede sumar a los graficos de rendimiento (inflacion y dolar MEP).
//
// Fuentes (todas oficiales, sin intermediarios):
//   - Inflacion: INDEC, IPC Nivel General Nacional (base dic 2016), publicado
//     por la API de Series de Tiempo del Estado nacional (datos.gob.ar).
//     Se cruza contra la "Inflacion mensual" que publica el BCRA.
//   - Dolar MEP: Indice Dolar BYMA, el indice de referencia que calcula y
//     publica el mercado (BYMA). Requiere credenciales de la API de BYMA,
//     cargadas como secretos del repo: BYMA_CLIENT_ID y BYMA_CLIENT_SECRET.
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
const BYMA_TOKEN = 'https://apigw.byma.com.ar/oauth/token/';
const BYMA_EOD = 'https://apigw.byma.com.ar/indice-dolar-byma/v1/eod.json';

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

// ---- Dolar MEP: Indice Dolar BYMA (cierre diario)
async function mepByma(){
  const id = process.env.BYMA_CLIENT_ID, secreto = process.env.BYMA_CLIENT_SECRET;
  if(!id || !secreto) throw new Error('faltan los secretos BYMA_CLIENT_ID y BYMA_CLIENT_SECRET');
  const cuerpo = new URLSearchParams({ grant_type: 'client_credentials', client_id: id, client_secret: secreto, scope: 'indiceDolarBYMA.eod.read' });
  const tok = await traerJson(BYMA_TOKEN, { method: 'POST', body: cuerpo, headers: { 'content-type': 'application/x-www-form-urlencoded' } });
  if(!tok.access_token) throw new Error('BYMA no devolvio token');
  const j = await traerJson(BYMA_EOD, { headers: { authorization: `bearer ${tok.access_token}` } });
  const datos = (j.result || [])
    .filter(f => f && f.date && Number.isFinite(Number(f.bymaClosingPrice)) && Number(f.bymaClosingPrice) > 0)
    .map(f => [String(f.date).slice(0, 10), Number(Number(f.bymaClosingPrice).toFixed(2))])
    .sort((a, b) => a[0] < b[0] ? -1 : 1);
  if(datos.length < 100) throw new Error(`Indice Dolar BYMA: solo ${datos.length} ruedas`);
  for(let i = 1; i < datos.length; i++){
    const v = datos[i][1] / datos[i - 1][1] - 1;
    if(!(v > -0.25 && v < 0.35)) throw new Error(`Indice Dolar BYMA: salto fuera de rango el ${datos[i][0]}`);
  }
  return datos;
}

// ---- Solo para probar conectividad desde el runner (no escribe nada)
async function probar(){
  const pruebas = {
    'datos.gob.ar (INDEC IPC)': () => inflacionIndec().then(d => `${d.length} meses, ultimo ${d.at(-1)}`),
    'BCRA inflacion mensual': () => traerJson(URL_BCRA_INFLACION).then(j => JSON.stringify(j.results[0].detalle.slice(0, 2))),
    'BYMA apigw (token sin credenciales)': () => fetch(BYMA_TOKEN, { method: 'POST' }).then(r => `HTTP ${r.status}`),
    'BYMA open data AL30': () => fetch(`https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/chart/historical-series/history?symbol=AL30%2024HS&resolution=D&from=${Math.floor(Date.now() / 1000) - 20 * 86400}&to=${Math.floor(Date.now() / 1000)}`).then(async r => `HTTP ${r.status} ${(await r.text()).slice(0, 300)}`),
    'BYMA open data AL30D': () => fetch(`https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/chart/historical-series/history?symbol=AL30D%2024HS&resolution=D&from=${Math.floor(Date.now() / 1000) - 20 * 86400}&to=${Math.floor(Date.now() / 1000)}`).then(async r => `HTTP ${r.status} ${(await r.text()).slice(0, 300)}`),
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
  const salida = { inflacion: previo.inflacion || null, mep: previo.mep || null };
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
    const datos = (await mepByma()).filter(f => f[0] >= DESDE);
    salida.mep = { fuente: 'BYMA, Índice Dólar BYMA (cierre diario)', via: 'API de BYMA', datos };
    console.log(`Dolar MEP: ${datos.length} ruedas, ultima ${datos.at(-1)[0]}`);
  } catch(e){ fallas++; console.log('::warning::Dolar MEP sin actualizar:', e.message); }

  const cuerpo = JSON.stringify({ inflacion: salida.inflacion, mep: salida.mep });
  const cuerpoPrevio = JSON.stringify({ inflacion: previo.inflacion || null, mep: previo.mep || null });
  if(cuerpo === cuerpoPrevio){ console.log('Sin cambios en los datos.'); return; }
  const out = { actualizado: new Date().toISOString(), ...salida };
  await writeFile(ARCHIVO, JSON.stringify(out) + '\n');
  console.log(`${ARCHIVO} actualizado (${fallas} fuente(s) con falla).`);
}

main().catch(e => { console.error(e); process.exit(1); });
