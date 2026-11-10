/* Proxy de datos de mercado para el termometro de la calculadora.

   Junta del lado del servidor las fuentes publicas que usa la pagina y las
   devuelve en una sola respuesta, ya normalizada:

     { generado, dolares:{ mep, ccl, mayorista, fecha, fechaMayorista },
       riesgoPais:{ valor, fecha },
       bcra:{ a3500, a3500Fecha, rem, remFecha },
       futuros:{ fecha, contratos:[{ venc, precio }] } }

   Asi el navegador no depende de que cada fuente permita pedidos desde otro
   dominio (CORS), y Vercel cachea la respuesta 15 minutos. Si una fuente
   falla, su bloque simplemente no viene: la pagina valida cada dato y, si
   falta o no pasa, usa lo cargado en comercial.xlsx. No guarda ni recibe
   ningun dato de la pagina. */

const FUENTES = {
  dolares: 'https://dolarapi.com/v1/dolares',
  riesgoPais: 'https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo',
  bcra: 'https://api.bcra.gob.ar/estadisticas/v4.0/monetarias',
  futuros: 'https://apicem.matbarofex.com.ar/api/v2/closing-prices',
};

async function traer(url, ms = 7000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(url, { signal: ctrl.signal, headers: { accept: 'application/json' } });
    return r.ok ? await r.json() : null;
  } catch (e) {
    return null;
  } finally {
    clearTimeout(t);
  }
}

// "DLR112027" -> ultimo dia habil de noviembre 2027
function vencimiento(simbolo) {
  const m = String(simbolo || '').match(/^DLR(\d{2})(\d{4})$/);
  if (!m) return null;
  const d = new Date(Date.UTC(Number(m[2]), Number(m[1]), 0));
  while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

module.exports = async (req, res) => {
  const iso = (d) => d.toISOString().slice(0, 10);
  const hasta = new Date();
  const desde = new Date(hasta.getTime() - 10 * 86400000);
  const urlFuturos = `${FUENTES.futuros}?product=DLR&segment=Monedas&type=FUT&excludeEmptyVol=false`
    + `&from=${iso(desde)}&to=${iso(hasta)}&page=1&pageSize=200&sortDir=DESC`;

  const [dol, rp, bcra, fut] = await Promise.all([
    traer(FUENTES.dolares), traer(FUENTES.riesgoPais), traer(FUENTES.bcra), traer(urlFuturos),
  ]);

  const out = { generado: new Date().toISOString() };

  if (Array.isArray(dol)) {
    const casa = (c) => dol.find((x) => x && x.casa === c) || {};
    out.dolares = {
      mep: Number(casa('bolsa').venta) || null,
      ccl: Number(casa('contadoconliqui').venta) || null,
      mayorista: Number(casa('mayorista').venta) || null,
      fecha: casa('bolsa').fechaActualizacion || null,
      fechaMayorista: casa('mayorista').fechaActualizacion || null,
    };
  }

  if (rp && rp.valor != null) out.riesgoPais = { valor: Number(rp.valor), fecha: rp.fecha || null };

  if (bcra && Array.isArray(bcra.results)) {
    const v = (id) => bcra.results.find((x) => x && x.idVariable === id) || {};
    out.bcra = {
      a3500: Number(v(5).ultValorInformado) || null,
      a3500Fecha: v(5).ultFechaInformada || null,
      rem: Number(v(29).ultValorInformado) || null,
      remFecha: v(29).ultFechaInformada || null,
    };
  }

  if (fut && Array.isArray(fut.data) && fut.data.length) {
    const ultima = fut.data.map((x) => String(x.dateTime || '').slice(0, 10)).sort().pop();
    out.futuros = {
      fecha: ultima,
      contratos: fut.data
        .filter((x) => String(x.dateTime || '').slice(0, 10) === ultima)
        .map((x) => ({ venc: vencimiento(x.symbol), precio: Number(x.settlement) }))
        .filter((x) => x.venc && x.precio > 0)
        .sort((a, b) => (a.venc < b.venc ? -1 : 1)),
    };
  }

  res.setHeader('Cache-Control', 's-maxage=900, stale-while-revalidate=3600');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.status(200).send(JSON.stringify(out));
};
