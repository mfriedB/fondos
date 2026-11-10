/* Series historicas para el Comparador de Fondos.

   Devuelve, ya recortadas a los ultimos tres años:
     { generado, mep:[{ fecha, venta }], inflacion:[{ fecha, valor }] }
   - mep: cierre diario del dolar MEP
   - inflacion: variacion mensual del IPC, en %

   La fuente es argentinadatos.com. Pasa por aca para que el navegador no
   dependa de que la fuente permita pedidos desde otro dominio y para que
   Vercel cachee la respuesta. Si falla, la pagina le pide las series directo
   a la fuente; si eso tambien falla, las lineas no se muestran. */

const FUENTES = {
  mep: 'https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa',
  inflacion: 'https://api.argentinadatos.com/v1/finanzas/indices/inflacion',
};

async function traer(url, ms = 9000) {
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

module.exports = async (req, res) => {
  const desde = new Date(Date.now() - 3 * 365 * 86400000).toISOString().slice(0, 10);
  const [mep, inflacion] = await Promise.all([traer(FUENTES.mep), traer(FUENTES.inflacion)]);
  const out = { generado: new Date().toISOString(), mep: [], inflacion: [] };
  if (Array.isArray(mep)) {
    out.mep = mep
      .filter((x) => x && x.fecha >= desde && Number(x.venta) > 0)
      .map((x) => ({ fecha: x.fecha, venta: Number(x.venta) }));
  }
  if (Array.isArray(inflacion)) {
    out.inflacion = inflacion
      .filter((x) => x && x.fecha >= desde && Number.isFinite(Number(x.valor)))
      .map((x) => ({ fecha: x.fecha, valor: Number(x.valor) }));
  }
  res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.status(200).send(JSON.stringify(out));
};
