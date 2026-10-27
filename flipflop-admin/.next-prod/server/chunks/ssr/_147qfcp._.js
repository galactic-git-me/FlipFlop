module.exports=[73340,a=>{"use strict";var b=a.i(87924),c=a.i(72131),d=a.i(50944),e=a.i(74746),f=a.i(92378),g=a.i(55681),h=a.i(3130);a.s(["default",0,function(){let a=(0,d.useParams)(),i=(0,d.useRouter)(),j=a.id,[k,l]=(0,c.useState)({title:"Stunning Ryzen 7 7800X3D | RTX 3070 | 32GB DDR5 | Windows 11 Pro",description:"Experience elite gaming and demanding productivity with this pristine, high-end custom-built PC. Everything included is top-tier, meticulously assembled, and guaranteed to run games and applications at the highest settings.",keyFeatures:["**CPU:** AMD Ryzen 7 7800X3D - The king of gaming CPUs, offering unmatched performance.","**GPU:** Palit RTX 3070 8GB - Perfect for high-refresh-rate 1440p gaming.","**Memory:** 32GB DDR5 6400MHz - Massive headroom for multitasking and future-proofing.","**Storage:** 1TB M.2 NVMe SSD - Lightning-fast boot times and load speeds.","**Motherboard:** ASUS PRIME X870-P - Robust platform for excellent stability.","**Cooling & Aesthetics:** Featuring the gorgeous APNX ChromaFlair Iridescent Chassis, white ARGB components (Thermalright Cooler & 6x Fans), and illuminated GPU bracket. This machine is as beautiful as powerful!","**Power:** Corsair RM750i Gold PSU - Reliable, fully modular power delivery.","**OS:** Includes Windows 11 Pro (Activated)."],perfectFor:["High-refresh-rate gaming (1080p/1440p)","Video editing and content creation","3D rendering and 3D modeling","Streaming to Twitch/YouTube","Multitasking power users"],warranty:"30-day money-back guarantee. All components tested and working perfectly.",shipping:"Fully insured shipping. Careful packaging to ensure safe arrival."}),[m,n]=(0,c.useState)(!1),[o,p]=(0,c.useState)(null),q=async a=>{n(!0),p(a);try{let b=await fetch(`/api/builds/${j}/publish`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({target:a,listing:k})});if(b.ok)if(alert(`Published to ${"ebay"===a?"eBay":"FlipFlop.shop"}!`),"ebay"===a){let a=await b.json();window.open(a.ebayUrl,"_blank")}else i.push(`/builds/${j}`)}catch(a){alert("Failed to publish. Please try again."),console.error(a)}finally{n(!1),p(null)}};return(0,b.jsx)("div",{className:"min-h-screen bg-[#0a0f1a]",children:(0,b.jsxs)("div",{className:"p-6 space-y-6",children:[(0,b.jsxs)("div",{children:[(0,b.jsx)("h1",{className:"text-3xl font-bold text-white mb-2",children:"Sell This Build"}),(0,b.jsx)("p",{className:"text-sm text-slate-400",children:"Create your eBay listing or publish to FlipFlop.shop"})]}),(0,b.jsxs)("div",{className:"grid grid-cols-1 lg:grid-cols-[1fr_1.1fr] gap-6",children:[(0,b.jsxs)("div",{className:"space-y-4 max-h-[calc(100vh-300px)] overflow-y-auto",children:[(0,b.jsxs)(h.Card,{className:"bg-[#0f1620] border-slate-700",children:[(0,b.jsx)(h.CardHeader,{children:(0,b.jsx)(h.CardTitle,{className:"text-sm text-white",children:"Listing Title"})}),(0,b.jsxs)(h.CardContent,{children:[(0,b.jsx)("textarea",{value:k.title,onChange:a=>l({...k,title:a.target.value}),className:"w-full px-3 py-2 bg-[#141d2d] border border-slate-600 rounded text-sm text-slate-300 outline-none focus:border-orange-400 resize-none",rows:3}),(0,b.jsxs)("p",{className:"text-xs text-slate-500 mt-2",children:[k.title.length,"/80 characters recommended"]})]})]}),(0,b.jsxs)(h.Card,{className:"bg-[#0f1620] border-slate-700",children:[(0,b.jsx)(h.CardHeader,{children:(0,b.jsx)(h.CardTitle,{className:"text-sm text-white",children:"Description"})}),(0,b.jsx)(h.CardContent,{children:(0,b.jsx)("textarea",{value:k.description,onChange:a=>l({...k,description:a.target.value}),className:"w-full px-3 py-2 bg-[#141d2d] border border-slate-600 rounded text-sm text-slate-300 outline-none focus:border-orange-400 resize-none",rows:6})})]}),(0,b.jsxs)(h.Card,{className:"bg-[#0f1620] border-slate-700",children:[(0,b.jsx)(h.CardHeader,{children:(0,b.jsx)(h.CardTitle,{className:"text-sm text-white",children:"Key Features"})}),(0,b.jsx)(h.CardContent,{className:"space-y-2",children:k.keyFeatures.map((a,c)=>(0,b.jsx)("div",{className:"flex gap-2",children:(0,b.jsx)("input",{type:"text",value:a,onChange:a=>{let b=[...k.keyFeatures];b[c]=a.target.value,l({...k,keyFeatures:b})},className:"flex-1 px-3 py-2 bg-[#141d2d] border border-slate-600 rounded text-xs text-slate-300 outline-none focus:border-orange-400"})},c))})]}),(0,b.jsxs)(h.Card,{className:"bg-[#0f1620] border-slate-700",children:[(0,b.jsx)(h.CardHeader,{children:(0,b.jsx)(h.CardTitle,{className:"text-sm text-white",children:"Warranty & Returns"})}),(0,b.jsx)(h.CardContent,{children:(0,b.jsx)("textarea",{value:k.warranty,onChange:a=>l({...k,warranty:a.target.value}),className:"w-full px-3 py-2 bg-[#141d2d] border border-slate-600 rounded text-sm text-slate-300 outline-none focus:border-orange-400 resize-none",rows:3})})]})]}),(0,b.jsxs)("div",{className:"hidden lg:flex sticky top-6 h-[calc(100vh-200px)] overflow-hidden flex-col",children:[(0,b.jsxs)("div",{className:"border border-orange-400/30 bg-orange-400/5 rounded-lg p-3 mb-4",children:[(0,b.jsxs)("div",{className:"flex items-center gap-2 mb-2",children:[(0,b.jsx)(g.Eye,{size:16,className:"text-orange-400"}),(0,b.jsx)("h2",{className:"text-xs font-bold text-orange-400 uppercase",children:"Live eBay Preview"})]}),(0,b.jsx)("p",{className:"text-xs text-slate-400",children:"This is how your listing will appear to eBay buyers"})]}),(0,b.jsx)("div",{className:"flex-1 bg-white rounded-lg overflow-hidden shadow-2xl border border-slate-200",children:(0,b.jsx)("iframe",{srcDoc:`
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>${k.title}</title>
    <style>
        body { font-family: Arial, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px; margin: 0; }
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
        p { margin: 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">FlipFlop</div>
            <div class="tagline">Beautiful Machines Built to Be Admired</div>
        </div>

        <h1>${k.title}</h1>

        <div class="description">${k.description}</div>

        <div class="section section-blue">
            <h2>✨ Key Features</h2>
            <ul>
                ${k.keyFeatures.map(a=>`<li>${a.replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>")}</li>`).join("")}
            </ul>
        </div>

        ${k.perfectFor&&k.perfectFor.length>0?`
        <div class="section">
            <h2>🎮 Perfect For</h2>
            <ul>
                ${k.perfectFor.map(a=>`<li>• ${a}</li>`).join("")}
            </ul>
        </div>
        `:""}

        <div class="section section-orange">
            <h2>🛡️ Warranty & Returns</h2>
            <p>${k.warranty}</p>
        </div>

        <div class="section">
            <h2>📦 Shipping</h2>
            <p>${k.shipping}</p>
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
  `.trim(),className:"w-full h-full border-0",title:"eBay Listing Preview"})})]})]}),(0,b.jsx)("div",{className:"fixed bottom-0 left-0 right-0 bg-gradient-to-t from-[#0a0f1a] via-[#0a0f1a] to-transparent p-6 border-t border-slate-700",children:(0,b.jsxs)("div",{className:"max-w-7xl mx-auto flex gap-3 justify-end",children:[(0,b.jsx)("button",{onClick:()=>i.back(),className:"px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors",disabled:m,children:"Cancel"}),(0,b.jsxs)("button",{onClick:()=>q("flipflop"),disabled:m,className:"flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50",children:[(0,b.jsx)(f.Zap,{size:16}),m&&"flipflop"===o?"Publishing...":"Publish to FlipFlop.shop"]}),(0,b.jsxs)("button",{onClick:()=>q("ebay"),disabled:m,className:"flex items-center gap-2 px-8 py-3 bg-gradient-to-r from-orange-400 to-orange-600 hover:from-orange-500 hover:to-orange-700 text-white rounded-lg font-bold transition-colors disabled:opacity-50",children:[(0,b.jsx)(e.Send,{size:16}),m&&"ebay"===o?"Publishing...":"Publish to eBay"]})]})})]})})}])},3130,a=>{"use strict";var b=a.i(87924),c=a.i(97895);a.s(["Card",0,function({children:a,className:d,hover:e,glow:f,onClick:g}){return(0,b.jsx)("div",{onClick:g,className:(0,c.cn)("rounded-xl glass-card",e&&"card-hover cursor-pointer",f&&"shadow-[0_0_20px_rgba(0,220,130,0.08)]",d),children:a})},"CardContent",0,function({children:a,className:d}){return(0,b.jsx)("div",{className:(0,c.cn)("px-5 pb-5",d),children:a})},"CardHeader",0,function({children:a,className:d}){return(0,b.jsx)("div",{className:(0,c.cn)("px-5 pt-5 pb-3",d),children:a})},"CardTitle",0,function({children:a,className:d}){return(0,b.jsx)("h3",{className:(0,c.cn)("text-sm font-semibold text-slate-200 tracking-wide",d),children:a})}])},55681,a=>{"use strict";let b=(0,a.i(64831).default)("eye",[["path",{d:"M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0",key:"1nclc0"}],["circle",{cx:"12",cy:"12",r:"3",key:"1v7zrd"}]]);a.s(["Eye",0,b],55681)}];

//# sourceMappingURL=_147qfcp._.js.map