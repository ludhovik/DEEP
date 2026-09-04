const ALLOWED_ORIGINS = new Set([
  "https://ludhovik.github.io",
]);

function corsHeaders(origin) {
  const allowed =
    ALLOWED_ORIGINS.has(origin) ||
    origin.startsWith("http://localhost:") ||
    origin.startsWith("http://127.0.0.1:");

  return {
    ...(allowed ? { "Access-Control-Allow-Origin": origin } : {}),
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin") || "";

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(origin),
      });
    }

    if (request.method !== "GET") {
      return new Response("Method not allowed", {
        status: 405,
        headers: corsHeaders(origin),
      });
    }

    const match = url.pathname.match(
      /^\/figshare\/articles\/([0-9]+)\/?$/
    );

    if (!match) {
      return new Response(
        "Use /figshare/articles/ARTICLE_ID",
        {
          status: 404,
          headers: corsHeaders(origin),
        }
      );
    }

    const articleId = match[1];
    const upstreamUrl =
      `https://api.figshare.com/v2/articles/${articleId}`;

    try {
      const upstream = await fetch(upstreamUrl, {
        headers: {
          "Accept": "application/json",
          "User-Agent": "DEEP-Figshare-Proxy/1.0",
        },
        cf: {
          cacheEverything: true,
          cacheTtl: 3600,
        },
      });

      const headers = new Headers(corsHeaders(origin));
      headers.set(
        "Content-Type",
        upstream.headers.get("Content-Type") ||
          "application/json"
      );
      headers.set("Cache-Control", "public, max-age=3600");

      return new Response(upstream.body, {
        status: upstream.status,
        statusText: upstream.statusText,
        headers,
      });
    } catch (error) {
      return Response.json(
        {
          error: "Could not contact Figshare",
          detail: String(error?.message || error),
        },
        {
          status: 502,
          headers: corsHeaders(origin),
        }
      );
    }
  },
};
