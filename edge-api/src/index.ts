export interface Env {
  APP_NAME: string;
  COURSE_NAME: string;
  OWNER: string;
  API_TOKEN: string;
  ADMIN_EMAIL: string;
  SETTINGS: KVNamespace;
}

const VERSION = "1.0.1";
const STARTED_AT = new Date().toISOString();

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    console.log("request", request.method, path, "colo", request.cf?.colo, "country", request.cf?.country);

    if (path === "/" || path === "/info") {
      return json({
        app: env.APP_NAME,
        course: env.COURSE_NAME,
        owner: env.OWNER,
        version: VERSION,
        startedAt: STARTED_AT,
        message: "Hello from Cloudflare Workers — DevOps Core Lab 17",
        routes: ["/", "/health", "/edge", "/counter", "/admin"],
        timestamp: new Date().toISOString(),
      });
    }

    if (path === "/health") {
      return json({
        status: "ok",
        app: env.APP_NAME,
        version: VERSION,
        timestamp: new Date().toISOString(),
      });
    }

    if (path === "/edge") {
      const cf = request.cf;
      return json({
        colo: cf?.colo,
        country: cf?.country,
        city: cf?.city,
        region: cf?.region,
        continent: cf?.continent,
        timezone: cf?.timezone,
        asn: cf?.asn,
        asOrganization: cf?.asOrganization,
        httpProtocol: cf?.httpProtocol,
        tlsVersion: cf?.tlsVersion,
        tlsCipher: cf?.tlsCipher,
      });
    }

    if (path === "/counter") {
      const raw = await env.SETTINGS.get("visits");
      const visits = Number(raw ?? "0") + 1;
      await env.SETTINGS.put("visits", String(visits));
      return json({
        visits,
        key: "visits",
        binding: "SETTINGS",
        message: "KV-backed counter; persists across deploys",
      });
    }

    if (path === "/admin") {
      const auth = request.headers.get("authorization") ?? "";
      const expected = `Bearer ${env.API_TOKEN}`;
      if (auth !== expected) {
        return json({ error: "unauthorized" }, 401);
      }
      return json({
        admin: env.ADMIN_EMAIL,
        app: env.APP_NAME,
        message: "authorized via secret API_TOKEN",
      });
    }

    return json({ error: "not_found", path }, 404);
  },
} satisfies ExportedHandler<Env>;
