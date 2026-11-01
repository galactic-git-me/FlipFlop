module.exports = [
"[externals]/next/dist/compiled/@opentelemetry/api [external] (next/dist/compiled/@opentelemetry/api, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("next/dist/compiled/@opentelemetry/api", () => require("next/dist/compiled/@opentelemetry/api"));

module.exports = mod;
}),
"[externals]/next/dist/compiled/next-server/app-page-turbo.runtime.dev.js [external] (next/dist/compiled/next-server/app-page-turbo.runtime.dev.js, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("next/dist/compiled/next-server/app-page-turbo.runtime.dev.js", () => require("next/dist/compiled/next-server/app-page-turbo.runtime.dev.js"));

module.exports = mod;
}),
"[externals]/next/dist/compiled/next-server/app-route-turbo.runtime.dev.js [external] (next/dist/compiled/next-server/app-route-turbo.runtime.dev.js, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("next/dist/compiled/next-server/app-route-turbo.runtime.dev.js", () => require("next/dist/compiled/next-server/app-route-turbo.runtime.dev.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/action-async-storage.external.js [external] (next/dist/server/app-render/action-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("next/dist/server/app-render/action-async-storage.external.js", () => require("next/dist/server/app-render/action-async-storage.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/after-task-async-storage.external.js [external] (next/dist/server/app-render/after-task-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("next/dist/server/app-render/after-task-async-storage.external.js", () => require("next/dist/server/app-render/after-task-async-storage.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/work-async-storage.external.js [external] (next/dist/server/app-render/work-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("next/dist/server/app-render/work-async-storage.external.js", () => require("next/dist/server/app-render/work-async-storage.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/work-unit-async-storage.external.js [external] (next/dist/server/app-render/work-unit-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("next/dist/server/app-render/work-unit-async-storage.external.js", () => require("next/dist/server/app-render/work-unit-async-storage.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/runtime-reacts.external.js [external] (next/dist/server/runtime-reacts.external.js, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("next/dist/server/runtime-reacts.external.js", () => require("next/dist/server/runtime-reacts.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/shared/lib/no-fallback-error.external.js [external] (next/dist/shared/lib/no-fallback-error.external.js, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("next/dist/shared/lib/no-fallback-error.external.js", () => require("next/dist/shared/lib/no-fallback-error.external.js"));

module.exports = mod;
}),
"[externals]/node:stream [external] (node:stream, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("node:stream", () => require("node:stream"));

module.exports = mod;
}),
"[project]/app/proxy-api/[...path]/route.ts [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "DELETE",
    ()=>DELETE,
    "GET",
    ()=>GET,
    "HEAD",
    ()=>HEAD,
    "PATCH",
    ()=>PATCH,
    "POST",
    ()=>POST,
    "PUT",
    ()=>PUT
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/server.js [app-route] (ecmascript)");
;
const backendUrl = (process.env.BACKEND_URL ?? "http://localhost:4314").replace(/\/$/, "");
const ebayOpsBackendUrl = (process.env.EBAY_OPS_BACKEND_URL ?? "").replace(/\/$/, "");
function backendForPath(path) {
    if (!ebayOpsBackendUrl) return backendUrl;
    const value = path.join("/");
    // Keep all local development operations on the configured local backend.
    // A deployed operations backend is an explicit deployment override only.
    if (value === "ebay/oauth/authorize-url" || value === "ebay/oauth/status" || value === "ebay/oauth/disconnect" || value === "manual-builds/ebay-fulfillment-policies" || /^manual-builds\/[^/]+\/(post-to-ebay|publish-ebay-draft|ebay-listing|sync-ebay-order)$/.test(value)) {
        return ebayOpsBackendUrl;
    }
    return backendUrl;
}
// Same-origin REST proxy. proxy attaches Authorization from the
// httpOnly admin_session cookie before this handler forwards to FastAPI.
async function forward(request, context) {
    const { path } = await context.params;
    const target = `${backendForPath(path)}/api/${path.join("/")}${request.nextUrl.search}`;
    const headers = new Headers();
    for (const name of [
        "authorization",
        "content-type",
        "accept",
        "range"
    ]){
        const value = request.headers.get(name);
        if (value) headers.set(name, value);
    }
    // Do not rely solely on proxy: in some Next/Turbopack deployments the
    // request header override is not preserved when entering an App Router
    // handler. Read the session cookie here as the authoritative fallback.
    if (!headers.has("authorization")) {
        const cookieHeader = request.headers.get("cookie") ?? "";
        const cookieValue = (name)=>cookieHeader.split(";").map((part)=>part.trim()).find((part)=>part.startsWith(`${name}=`))?.slice(name.length + 1);
        const token = cookieValue("admin_session") ?? cookieValue("admin_token");
        if (token) headers.set("authorization", `Bearer ${token}`);
    }
    const fetchOptions = {
        method: request.method,
        headers,
        body: [
            "GET",
            "HEAD"
        ].includes(request.method) ? undefined : await request.arrayBuffer(),
        redirect: "manual",
        signal: AbortSignal.timeout(120_000)
    };
    // The public production endpoint sits behind Caddy and can occasionally
    // reset an idle HTTP connection. Retry once so a transient reset does not
    // surface to the browser as the opaque `TypeError: Failed to fetch`.
    let response;
    try {
        response = await fetch(target, fetchOptions);
    } catch (error) {
        try {
            response = await fetch(target, fetchOptions);
        } catch (retryError) {
            console.error(`[proxy-api] upstream unavailable: ${target}`, retryError ?? error);
            return __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
                detail: "Backend API is unavailable",
                upstream: target
            }, {
                status: 502
            });
        }
    }
    // Preserve Authorization across backend canonical-host/trailing-slash
    // redirects. Native fetch can drop it when following to another origin.
    for(let hop = 0; hop < 3 && response.status >= 300 && response.status < 400; hop += 1){
        const location = response.headers.get("location");
        if (!location) break;
        response = await fetch(new URL(location, target), fetchOptions);
    }
    const responseHeaders = new Headers();
    for (const name of [
        "content-type",
        "content-disposition"
    ]){
        const value = response.headers.get(name);
        if (value) responseHeaders.set(name, value);
    }
    return new __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"](response.body, {
        status: response.status,
        headers: responseHeaders
    });
}
const GET = forward;
const HEAD = forward;
const POST = forward;
const PUT = forward;
const PATCH = forward;
const DELETE = forward;
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__0xad-hw._.js.map