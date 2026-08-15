/**
 * Runtime proxy — forwards /api/* to the FastAPI backend.
 *
 * Why this exists instead of next.config.ts rewrites:
 *   async rewrites() is evaluated at `next build` time. The BACKEND_URL env
 *   var set on Cloud Run is only available at runtime, so the rewrite was being
 *   baked with the build-time default (localhost:8000) and every call was
 *   silently falling back to the offline mock.
 *
 *   This route.ts runs inside the live Node.js server and reads BACKEND_URL
 *   at each request — no baking, no stale URLs.
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND = (process.env.BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '');

type Context = { params: Promise<{ proxy: string[] }> };

async function handler(request: NextRequest, context: Context): Promise<NextResponse> {
  const { proxy } = await context.params;
  const path = proxy.join('/');

  // Preserve query string (for GET /aggregate?sector=water_sanitation etc.)
  const target = new URL(`${BACKEND}/${path}`);
  request.nextUrl.searchParams.forEach((v, k) => target.searchParams.set(k, v));

  const headers = new Headers(request.headers);
  headers.delete('host');       // must not forward — would confuse the API
  headers.delete('connection');

  const init: RequestInit = { method: request.method, headers };
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = await request.blob();   // forward multipart, JSON, etc. as-is
    // @ts-expect-error — Next.js types don't expose duplex yet
    init.duplex = 'half';
  }

  let res: Response;
  try {
    res = await fetch(target.toString(), init);
  } catch (err) {
    return NextResponse.json(
      { error: 'API unreachable', detail: String(err) },
      { status: 502 },
    );
  }

  const body = await res.blob();
  return new NextResponse(body, {
    status: res.status,
    headers: { 'Content-Type': res.headers.get('Content-Type') ?? 'application/json' },
  });
}

export const GET    = handler;
export const POST   = handler;
export const PUT    = handler;
export const DELETE = handler;
