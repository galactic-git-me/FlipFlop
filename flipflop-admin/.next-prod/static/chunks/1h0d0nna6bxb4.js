(globalThis.TURBOPACK||(globalThis.TURBOPACK=[])).push(["object"==typeof document?document.currentScript:void 0,38956,e=>{"use strict";var t=e.i(43476),i=e.i(71645),r=e.i(18566),s=e.i(30274),a=e.i(64569),o=e.i(72382),l=e.i(70065);e.s(["default",0,function(){let e=(0,r.useParams)(),n=(0,r.useRouter)(),d=e.id,[c,p]=(0,i.useState)({title:"Stunning Ryzen 7 7800X3D | RTX 3070 | 32GB DDR5 | Windows 11 Pro",description:"Experience elite gaming and demanding productivity with this pristine, high-end custom-built PC. Everything included is top-tier, meticulously assembled, and guaranteed to run games and applications at the highest settings.",keyFeatures:["**CPU:** AMD Ryzen 7 7800X3D - The king of gaming CPUs, offering unmatched performance.","**GPU:** Palit RTX 3070 8GB - Perfect for high-refresh-rate 1440p gaming.","**Memory:** 32GB DDR5 6400MHz - Massive headroom for multitasking and future-proofing.","**Storage:** 1TB M.2 NVMe SSD - Lightning-fast boot times and load speeds.","**Motherboard:** ASUS PRIME X870-P - Robust platform for excellent stability.","**Cooling & Aesthetics:** Featuring the gorgeous APNX ChromaFlair Iridescent Chassis, white ARGB components (Thermalright Cooler & 6x Fans), and illuminated GPU bracket. This machine is as beautiful as powerful!","**Power:** Corsair RM750i Gold PSU - Reliable, fully modular power delivery.","**OS:** Includes Windows 11 Pro (Activated)."],perfectFor:["High-refresh-rate gaming (1080p/1440p)","Video editing and content creation","3D rendering and 3D modeling","Streaming to Twitch/YouTube","Multitasking power users"],warranty:"30-day money-back guarantee. All components tested and working perfectly.",shipping:"Fully insured shipping. Careful packaging to ensure safe arrival."}),[g,h]=(0,i.useState)(!1),[u,x]=(0,i.useState)(null),f=async e=>{h(!0),x(e);try{let t=await fetch(`/api/builds/${d}/publish`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({target:e,listing:c})});if(t.ok)if(alert(`Published to ${"ebay"===e?"eBay":"FlipFlop.shop"}!`),"ebay"===e){let e=await t.json();window.open(e.ebayUrl,"_blank")}else n.push(`/builds/${d}`)}catch(e){alert("Failed to publish. Please try again."),console.error(e)}finally{h(!1),x(null)}};return(0,t.jsx)("div",{className:"min-h-screen bg-[#0a0f1a]",children:(0,t.jsxs)("div",{className:"p-6 space-y-6",children:[(0,t.jsxs)("div",{children:[(0,t.jsx)("h1",{className:"text-3xl font-bold text-white mb-2",children:"Sell This Build"}),(0,t.jsx)("p",{className:"text-sm text-slate-400",children:"Create your eBay listing or publish to FlipFlop.shop"})]}),(0,t.jsxs)("div",{className:"grid grid-cols-1 lg:grid-cols-[1fr_1.1fr] gap-6",children:[(0,t.jsxs)("div",{className:"space-y-4 max-h-[calc(100vh-300px)] overflow-y-auto",children:[(0,t.jsxs)(l.Card,{className:"bg-[#0f1620] border-slate-700",children:[(0,t.jsx)(l.CardHeader,{children:(0,t.jsx)(l.CardTitle,{className:"text-sm text-white",children:"Listing Title"})}),(0,t.jsxs)(l.CardContent,{children:[(0,t.jsx)("textarea",{value:c.title,onChange:e=>p({...c,title:e.target.value}),className:"w-full px-3 py-2 bg-[#141d2d] border border-slate-600 rounded text-sm text-slate-300 outline-none focus:border-orange-400 resize-none",rows:3}),(0,t.jsxs)("p",{className:"text-xs text-slate-500 mt-2",children:[c.title.length,"/80 characters recommended"]})]})]}),(0,t.jsxs)(l.Card,{className:"bg-[#0f1620] border-slate-700",children:[(0,t.jsx)(l.CardHeader,{children:(0,t.jsx)(l.CardTitle,{className:"text-sm text-white",children:"Description"})}),(0,t.jsx)(l.CardContent,{children:(0,t.jsx)("textarea",{value:c.description,onChange:e=>p({...c,description:e.target.value}),className:"w-full px-3 py-2 bg-[#141d2d] border border-slate-600 rounded text-sm text-slate-300 outline-none focus:border-orange-400 resize-none",rows:6})})]}),(0,t.jsxs)(l.Card,{className:"bg-[#0f1620] border-slate-700",children:[(0,t.jsx)(l.CardHeader,{children:(0,t.jsx)(l.CardTitle,{className:"text-sm text-white",children:"Key Features"})}),(0,t.jsx)(l.CardContent,{className:"space-y-2",children:c.keyFeatures.map((e,i)=>(0,t.jsx)("div",{className:"flex gap-2",children:(0,t.jsx)("input",{type:"text",value:e,onChange:e=>{let t=[...c.keyFeatures];t[i]=e.target.value,p({...c,keyFeatures:t})},className:"flex-1 px-3 py-2 bg-[#141d2d] border border-slate-600 rounded text-xs text-slate-300 outline-none focus:border-orange-400"})},i))})]}),(0,t.jsxs)(l.Card,{className:"bg-[#0f1620] border-slate-700",children:[(0,t.jsx)(l.CardHeader,{children:(0,t.jsx)(l.CardTitle,{className:"text-sm text-white",children:"Warranty & Returns"})}),(0,t.jsx)(l.CardContent,{children:(0,t.jsx)("textarea",{value:c.warranty,onChange:e=>p({...c,warranty:e.target.value}),className:"w-full px-3 py-2 bg-[#141d2d] border border-slate-600 rounded text-sm text-slate-300 outline-none focus:border-orange-400 resize-none",rows:3})})]})]}),(0,t.jsxs)("div",{className:"hidden lg:flex sticky top-6 h-[calc(100vh-200px)] overflow-hidden flex-col",children:[(0,t.jsxs)("div",{className:"border border-orange-400/30 bg-orange-400/5 rounded-lg p-3 mb-4",children:[(0,t.jsxs)("div",{className:"flex items-center gap-2 mb-2",children:[(0,t.jsx)(o.Eye,{size:16,className:"text-orange-400"}),(0,t.jsx)("h2",{className:"text-xs font-bold text-orange-400 uppercase",children:"Live eBay Preview"})]}),(0,t.jsx)("p",{className:"text-xs text-slate-400",children:"This is how your listing will appear to eBay buyers"})]}),(0,t.jsx)("div",{className:"flex-1 bg-white rounded-lg overflow-hidden shadow-2xl border border-slate-200",children:(0,t.jsx)("iframe",{srcDoc:`
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>${c.title}</title>
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

        <h1>${c.title}</h1>

        <div class="description">${c.description}</div>

        <div class="section section-blue">
            <h2>✨ Key Features</h2>
            <ul>
                ${c.keyFeatures.map(e=>`<li>${e.replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>")}</li>`).join("")}
            </ul>
        </div>

        ${c.perfectFor&&c.perfectFor.length>0?`
        <div class="section">
            <h2>🎮 Perfect For</h2>
            <ul>
                ${c.perfectFor.map(e=>`<li>• ${e}</li>`).join("")}
            </ul>
        </div>
        `:""}

        <div class="section section-orange">
            <h2>🛡️ Warranty & Returns</h2>
            <p>${c.warranty}</p>
        </div>

        <div class="section">
            <h2>📦 Shipping</h2>
            <p>${c.shipping}</p>
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
  `.trim(),className:"w-full h-full border-0",title:"eBay Listing Preview"})})]})]}),(0,t.jsx)("div",{className:"fixed bottom-0 left-0 right-0 bg-gradient-to-t from-[#0a0f1a] via-[#0a0f1a] to-transparent p-6 border-t border-slate-700",children:(0,t.jsxs)("div",{className:"max-w-7xl mx-auto flex gap-3 justify-end",children:[(0,t.jsx)("button",{onClick:()=>n.back(),className:"px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors",disabled:g,children:"Cancel"}),(0,t.jsxs)("button",{onClick:()=>f("flipflop"),disabled:g,className:"flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50",children:[(0,t.jsx)(a.Zap,{size:16}),g&&"flipflop"===u?"Publishing...":"Publish to FlipFlop.shop"]}),(0,t.jsxs)("button",{onClick:()=>f("ebay"),disabled:g,className:"flex items-center gap-2 px-8 py-3 bg-gradient-to-r from-orange-400 to-orange-600 hover:from-orange-500 hover:to-orange-700 text-white rounded-lg font-bold transition-colors disabled:opacity-50",children:[(0,t.jsx)(s.Send,{size:16}),g&&"ebay"===u?"Publishing...":"Publish to eBay"]})]})})]})})}])},70065,e=>{"use strict";var t=e.i(43476),i=e.i(47163);e.s(["Card",0,function({children:e,className:r,hover:s,glow:a,onClick:o}){return(0,t.jsx)("div",{onClick:o,className:(0,i.cn)("rounded-xl glass-card",s&&"card-hover cursor-pointer",a&&"shadow-[0_0_20px_rgba(0,220,130,0.08)]",r),children:e})},"CardContent",0,function({children:e,className:r}){return(0,t.jsx)("div",{className:(0,i.cn)("px-5 pb-5",r),children:e})},"CardHeader",0,function({children:e,className:r}){return(0,t.jsx)("div",{className:(0,i.cn)("px-5 pt-5 pb-3",r),children:e})},"CardTitle",0,function({children:e,className:r}){return(0,t.jsx)("h3",{className:(0,i.cn)("text-sm font-semibold text-slate-200 tracking-wide",r),children:e})}])},72382,e=>{"use strict";let t=(0,e.i(56420).default)("eye",[["path",{d:"M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0",key:"1nclc0"}],["circle",{cx:"12",cy:"12",r:"3",key:"1v7zrd"}]]);e.s(["Eye",0,t],72382)}]);