module.exports=[38308,e=>{"use strict";var t=e.i(89171);async function i(e,{params:r}){try{let{id:i}=await r,a=await e.json();if(!a.target||!a.listing)return t.NextResponse.json({error:"Missing target or listing data"},{status:400});if("ebay"===a.target){var o;let e=(o=a.listing,`
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>${o.title}</title>
    <style>
        body { font-family: Arial, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; }
        .header { border-bottom: 3px solid #0066ff; padding-bottom: 20px; margin-bottom: 30px; }
        .logo { font-size: 24px; font-weight: bold; background: linear-gradient(135deg, #0066ff 0%, #ff6600 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }
        .tagline { font-size: 14px; color: #666; }
        h1 { font-size: 28px; font-weight: bold; margin: 30px 0 20px 0; color: #000; }
        h2 { font-size: 16px; font-weight: bold; margin: 20px 0 15px 0; color: #000; }
        .description { font-size: 14px; line-height: 1.8; color: #444; white-space: pre-wrap; margin-bottom: 30px; padding: 20px; background: #f8fafc; border-radius: 8px; }
        .section { margin-bottom: 30px; padding: 20px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; }
        .section-blue { border: 2px solid #0066ff; background: #f0f9ff; }
        .section-orange { border: 2px solid #ff6600; background: #fff9f0; }
        ul { list-style: none; padding: 0; margin: 0; }
        li { font-size: 14px; line-height: 1.7; color: #333; margin-bottom: 12px; padding-left: 24px; position: relative; }
        li:before { content: "▸"; position: absolute; left: 0; color: #0066ff; font-weight: bold; }
        .trust-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 20px; }
        .trust-item { padding: 16px; background: rgba(255,255,255,0.1); border-radius: 8px; text-align: center; color: white; font-size: 13px; }
        .trust-emoji { font-size: 24px; margin-bottom: 8px; }
        .footer { border-top: 2px solid #e2e8f0; padding-top: 20px; margin-top: 30px; text-align: center; font-size: 12px; color: #999; }
        strong { color: #0066ff; font-weight: 600; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">FlipFlop</div>
            <div class="tagline">Beautiful Machines Built to Be Admired</div>
        </div>

        <h1>${o.title}</h1>

        <div class="description">${o.description}</div>

        <div class="section section-blue">
            <h2>✨ Key Features</h2>
            <ul>
                ${o.keyFeatures.map(e=>`<li>${e.replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>")}</li>`).join("")}
            </ul>
        </div>

        ${o.perfectFor&&o.perfectFor.length>0?`
        <div class="section">
            <h2>🎮 Perfect For</h2>
            <ul>
                ${o.perfectFor.map(e=>`<li>• ${e}</li>`).join("")}
            </ul>
        </div>
        `:""}

        <div class="section section-orange">
            <h2>🛡️ Warranty & Returns</h2>
            <p>${o.warranty}</p>
        </div>

        <div class="section">
            <h2>📦 Shipping</h2>
            <p>${o.shipping}</p>
        </div>

        <div class="section" style="background: linear-gradient(135deg, #0066ff 0%, #ff6600 100%); color: white; border: none; text-align: center;">
            <h2 style="color: white;">💯 Why Buy From FlipFlop?</h2>
            <div class="trust-grid">
                <div class="trust-item">
                    <div class="trust-emoji">✓</div>
                    <div><strong style="color: white;">Fully Tested</strong></div>
                    <div>Every build verified</div>
                </div>
                <div class="trust-item">
                    <div class="trust-emoji">⚡</div>
                    <div><strong style="color: white;">Expert Built</strong></div>
                    <div>20+ years experience</div>
                </div>
                <div class="trust-item">
                    <div class="trust-emoji">💎</div>
                    <div><strong style="color: white;">Great Value</strong></div>
                    <div>Transparent pricing</div>
                </div>
            </div>
        </div>

        <div class="footer">
            <p>FlipFlop • Professional PC Builds • Every machine is inspected and tested before shipment.</p>
        </div>
    </div>
</body>
</html>
  `.trim());return console.log(`[eBay Publish] Build ${i}:`,{title:a.listing.title,htmlLength:e.length}),t.NextResponse.json({success:!0,target:"ebay",ebayUrl:"https://www.ebay.com/itm/123456789",message:"Listing prepared for eBay. Use the eBay API to publish.",html:e})}if("flipflop"!==a.target)return t.NextResponse.json({error:"Invalid target. Must be 'ebay' or 'flipflop'"},{status:400});{console.log(`[FlipFlop Publish] Build ${i}:`,{title:a.listing.title});let e=`/builds/${i}`;return t.NextResponse.json({success:!0,target:"flipflop",url:e,message:"Successfully published to FlipFlop.shop"})}}catch(e){return console.error("Publish error:",e),t.NextResponse.json({error:"Failed to publish listing"},{status:500})}}e.s(["POST",0,i])},98907,e=>{"use strict";var t=e.i(47909),i=e.i(74017),r=e.i(96250),o=e.i(59756),a=e.i(61916),n=e.i(74677),s=e.i(69741),l=e.i(16795),d=e.i(87718),p=e.i(95169),u=e.i(47587),c=e.i(66012),h=e.i(70101),g=e.i(26937),f=e.i(10372),v=e.i(93695);e.i(52474);var m=e.i(220);let b=new t.AppRouteRouteModule({definition:{kind:i.RouteKind.APP_ROUTE,page:"/api/builds/[id]/publish/route",pathname:"/api/builds/[id]/publish",filename:"route",bundlePath:""},distDir:".next-prod",relativeProjectDir:"",resolvedPagePath:"[project]/app/api/builds/[id]/publish/route.ts",nextConfigOutput:"",userland:()=>e.r(38308),...{}}),{workAsyncStorage:x,workUnitAsyncStorage:R,serverHooks:w}=b;async function y(e,t,r){r.requestMeta&&(0,o.setRequestMeta)(e,r.requestMeta),b.isDev&&(0,o.addRequestMeta)(e,"devRequestTimingInternalsEnd",process.hrtime.bigint());let x="/api/builds/[id]/publish/route";x=x.replace(/\/index$/,"")||"/";let R=await b.prepare(e,t,{srcPage:x,multiZoneDraftMode:!1});if(!R)return t.statusCode=400,t.end("Bad Request"),null==r.waitUntil||r.waitUntil.call(r,Promise.resolve()),null;let{buildId:w,deploymentId:y,params:E,nextConfig:C,parsedUrl:A,isDraftMode:P,prerenderManifest:T,routerServerContext:N,isOnDemandRevalidate:S,revalidateOnlyGenerated:F,resolvedPathname:k,clientReferenceManifest:O,serverActionsManifest:_}=R,$=(0,s.normalizeAppPath)(x),j=!!(T.dynamicRoutes[$]||T.routes[k]),q=async()=>((null==N?void 0:N.render404)?await N.render404(e,t,A,!1):t.end("This page could not be found"),null);if(j&&!P){let e=!!T.routes[k],t=T.dynamicRoutes[$];if(t&&!1===t.fallback&&!e){if(C.adapterPath)return await q();throw new v.NoFallbackError}}let H=null;!j||b.isDev||P||(H="/index"===(H=k)?"/":H);let I=!0===b.isDev||!j,M=j&&!I;_&&O&&(0,n.setManifestsSingleton)({page:x,clientReferenceManifest:O,serverActionsManifest:_});let U=e.method||"GET",B=(0,a.getTracer)(),D=B.getActiveScopeSpan(),z=!!(null==N?void 0:N.isWrappedByNextServer),K=!!(0,o.getRequestMeta)(e,"minimalMode"),L=(0,o.getRequestMeta)(e,"incrementalCache")||await b.getIncrementalCache(e,C,T,K);null==L||L.resetRequestCache(),globalThis.__incrementalCache=L;let G={params:E,previewProps:T.preview,renderOpts:{experimental:{authInterrupts:!!C.experimental.authInterrupts,useCacheTimeout:C.experimental.useCacheTimeout},cacheComponents:!!C.cacheComponents,validationLevel:C.experimental.instantInsights.validationLevel,supportsDynamicResponse:I,incrementalCache:L,hmrRefreshHash:(0,o.getRequestMeta)(e,"hmrRefreshHash"),cacheLifeProfiles:C.cacheLife,staticPageGenerationTimeout:C.staticPageGenerationTimeout,waitUntil:r.waitUntil,onClose:e=>{t.on("close",e)},onAfterTaskError:void 0,onInstrumentationRequestError:(t,i,r,o)=>b.onRequestError(e,t,r,o,N)},sharedContext:{buildId:w,deploymentId:y}},V=new l.NodeNextRequest(e),W=new l.NodeNextResponse(t),X=d.NextRequestAdapter.fromNodeNextRequest(V,(0,d.signalFromNodeResponse)(t)),Y=async({previousCacheEntry:i})=>{try{if(!K&&S&&F&&!i)return t.statusCode=404,t.setHeader("x-nextjs-cache","REVALIDATED"),t.end("This page could not be found"),null;let o=await b.handle(X,G);e.fetchMetrics=G.renderOpts.fetchMetrics;let a=G.renderOpts.pendingWaitUntil;a&&r.waitUntil&&(r.waitUntil(a),a=void 0);let n=G.renderOpts.collectedTags;if(!j)return await (0,c.sendResponse)(V,W,o,a),null;{let e=await o.blob(),t=(0,h.toNodeOutgoingHttpHeaders)(o.headers);n&&(t[f.NEXT_CACHE_TAGS_HEADER]=n),!t["content-type"]&&e.type&&(t["content-type"]=e.type);let i=void 0!==G.renderOpts.collectedRevalidate&&!(G.renderOpts.collectedRevalidate>=f.INFINITE_CACHE)&&G.renderOpts.collectedRevalidate,r=void 0===G.renderOpts.collectedExpire||G.renderOpts.collectedExpire>=f.INFINITE_CACHE?!1!==i&&i>0?C.expireTime:void 0:G.renderOpts.collectedExpire;return{value:{kind:m.CachedRouteKind.APP_ROUTE,status:o.status,body:Buffer.from(await e.arrayBuffer()),headers:t},cacheControl:{revalidate:i,expire:r}}}}catch(t){throw(null==i?void 0:i.isStale)&&await b.onRequestError(e,t,{routerKind:"App Router",routePath:x,routeType:"route",revalidateReason:(0,u.getRevalidateReason)({isStaticGeneration:M,isOnDemandRevalidate:S})},!1,N),t}},Z=async(o,n)=>{try{var s,l;let o=await b.handleResponse({req:e,nextConfig:C,cacheKey:H,routeKind:i.RouteKind.APP_ROUTE,isFallback:!1,prerenderManifest:T,isRoutePPREnabled:!1,isOnDemandRevalidate:S,revalidateOnlyGenerated:F,responseGenerator:Y,waitUntil:r.waitUntil,isMinimalMode:K});if(!j)return;if((null==o||null==(s=o.value)?void 0:s.kind)!==m.CachedRouteKind.APP_ROUTE)throw Object.defineProperty(Error(`Invariant: app-route received invalid cache entry ${null==o||null==(l=o.value)?void 0:l.kind}`),"__NEXT_ERROR_CODE",{value:"E701",enumerable:!1,configurable:!0});K||t.setHeader("x-nextjs-cache",S?"REVALIDATED":o.isMiss?"MISS":o.isStale?"STALE":"HIT"),P&&t.setHeader("Cache-Control","private, no-cache, no-store, max-age=0, must-revalidate");let a=(0,h.fromNodeOutgoingHttpHeaders)(o.value.headers);K&&j||a.delete(f.NEXT_CACHE_TAGS_HEADER),!o.cacheControl||t.getHeader("Cache-Control")||a.get("Cache-Control")||a.set("Cache-Control",(0,g.getCacheControlHeader)(o.cacheControl)),await (0,c.sendResponse)(V,W,new Response(o.value.body,{headers:a,status:o.value.status||200}));return}catch(t){if(t instanceof v.NoFallbackError||await b.onRequestError(e,t,{routerKind:"App Router",routePath:$,routeType:"route",revalidateReason:(0,u.getRevalidateReason)({isStaticGeneration:M,isOnDemandRevalidate:S})},!1,N),j)throw t;await (0,c.sendResponse)(V,W,new Response(null,{status:500}));return}finally{(()=>{if(!o)return;let e=t.statusCode;o.setAttributes({"http.status_code":e,"next.rsc":!1}),e&&e>=500&&(o.setStatus({code:a.SpanStatusCode.ERROR}),o.setAttribute("error.type",e.toString()));let i=B.getRootSpanAttributes();if(!i)return;if(i.get("next.span_type")!==p.BaseServerSpan.handleRequest)return console.warn(`Unexpected root span type '${i.get("next.span_type")}'. Please report this Next.js issue https://github.com/vercel/next.js`);let r=i.get("next.route")||$,s=`${U} ${r}`;o.setAttributes({"next.route":r,"http.route":r,"next.span_name":s}),o.updateName(s),n&&n!==o&&(n.setAttribute("http.route",r),n.updateName(s))})()}};if(z&&D)await Z(D,void 0);else{let t=B.getActiveScopeSpan();await B.withPropagatedContext(e.headers,()=>B.trace(p.BaseServerSpan.handleRequest,{spanName:`${U} ${x}`,kind:a.SpanKind.SERVER,attributes:{"http.method":U,"http.target":e.url}},e=>Z(e,t)),void 0,!z)}}e.s(["handler",0,y,"patchFetch",0,function(){return(0,r.patchFetch)({workAsyncStorage:x,workUnitAsyncStorage:R})},"routeModule",0,b,"serverHooks",0,w,"workAsyncStorage",0,x,"workUnitAsyncStorage",0,R])}];

//# sourceMappingURL=_1142-2j._.js.map