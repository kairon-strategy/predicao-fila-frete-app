import { type NextRequest, NextResponse } from "next/server";

/**
 * Guarda de auth no servidor (Next 16 — proxy.ts, ex-middleware).
 * Redireciona para /login quem não tem o flag de sessão (cookie kairon_auth).
 * O flag é só um portão de UX; a validação real do JWT é feita pela API.
 */
const PUBLIC_PATHS = ["/login", "/register"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  const authed = request.cookies.get("kairon_auth")?.value === "1";

  if (!authed && !isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  // Já logado tentando ver /login ou /register → manda pro dashboard.
  if (authed && isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // ignora assets do Next e arquivos estáticos (com extensão)
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
