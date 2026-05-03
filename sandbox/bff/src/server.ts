/**
 * Locus sandbox BFF.
 *
 * Thin Node forwarder between the SPA and the Python pattern runner. The
 * BFF exists so the browser sees one same-origin endpoint surface, secrets
 * never leave the dev's machine, and we can swap backends behind the
 * stable /api shape later.
 */
import express from "express";
import type { Request, Response } from "express";

const PORT = Number(process.env.PORT ?? 3001);
const RUNNER = (process.env.RUNNER_URL ?? "http://127.0.0.1:8100").replace(/\/$/, "");

const app = express();
app.use(express.json({ limit: "1mb" }));

async function forward(req: Request, res: Response, init: RequestInit): Promise<void> {
  const path = req.originalUrl;
  try {
    const upstream = await fetch(`${RUNNER}${path}`, init);
    const text = await upstream.text();
    res.status(upstream.status).type(upstream.headers.get("content-type") ?? "application/json").send(text);
  } catch (err) {
    res.status(502).json({ error: `bff: ${(err as Error).message}` });
  }
}

app.get("/api/health", async (_req, res) => {
  try {
    const r = await fetch(`${RUNNER}/api/health`);
    const body = await r.json();
    res.json({ ok: true, runner: body });
  } catch (err) {
    res.status(502).json({ ok: false, error: `runner: ${(err as Error).message}` });
  }
});

app.get("/api/patterns", (req, res) => {
  void forward(req, res, { method: "GET" });
});

app.post("/api/run/:pattern", (req, res) => {
  void forward(req, res, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req.body),
  });
});

app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`[bff] :${PORT} → runner ${RUNNER}`);
});
