# Create Pre-Built - Manual PC Entry Guide

## 🎯 What You Just Got

A complete **manual PC build entry system** that combines:
- ✅ Single-form component entry (all in one place)
- ✅ Real-time market price lookup (today's eBay prices)
- ✅ LLM component assessment (is it a good deal?)
- ✅ AI profit calculation (expected resale value)
- ✅ Build suggestions (upgrades that increase profit)

---

## 📍 Access the Feature

Navigate to your admin dashboard:

```
http://localhost:4312/add-build
```

Open **Pre-Built** in the left navigation, then choose **Create Pre-Built**.

---

## 🖥️ The Form

### 1. **Build Name**
Give your build an identifiable name:
- "Gaming PC #1"
- "Budget Office Workstation"  
- "Streaming Rig"

### 2. **Add Components** (Pre-populated with Required Parts)

The form starts with 5 **required components**:
- 🖥️ CPU / Processor
- 🔌 Motherboard
- 💾 RAM / Memory
- 💿 Storage (SSD/HDD)
- ⚡ Power Supply

Plus optional components:
- 🎮 Graphics Card (GPU)
- ❄️ CPU Cooler
- 📦 PC Case

### 3. **For Each Component, Enter:**

- **Component Name** - Be specific (not just "CPU", use "Intel Core i7-10700K")
- **Price Paid (£)** - What you actually paid
- **Condition** - New / Refurbished / Used
- **Source** - eBay, Amazon, Local store, etc.
- **Notes (Optional)** - "slight cosmetic damage", "includes original box"

---

## 🔍 Market Price Check

After entering a component name:

1. Click **"Check Price"** button next to the component
2. The system queries live eBay listings for that component
3. You'll see:
   - **Market Range** - Low to high prices found
   - **Fair Price** - Average current market price
   - **Deal Score** - Green (+) = you got a good deal; Orange (-) = overpaid

This helps you verify your pricing is competitive!

---

## 🤖 AI Evaluation (Automatic on Save)

When you click **"Save & Evaluate Build"**:

### The LLM Analyzes:

**1. Market Price Range Today**
- Conservative estimate (lowest you could sell for)
- Fair market price (realistic selling price)
- Optimistic estimate (best-case scenario)

**2. Profit Calculation**
- Investment: Total you paid
- Expected Resale: What LLM thinks you'll sell for
- Expected Profit: Actual £ profit
- ROI: Return on investment %
- Margin: Profit margin %

**3. Component-by-Component Assessment**
- Shows each component's market price vs. what you paid
- Flags if you overpaid on any part
- Shows component's weight in total build cost

**4. AI Narrative**
The LLM gives you a written assessment like:
> "This is a solid mid-range gaming build. The CPU and RAM are good value, but you paid slightly over market on the GPU. Overall, expect to sell for £850-950 with good demand in Q1 2025."

**5. Enhancement Suggestions**
AI recommends upgrades that increase profit:
> "Adding a 1TB SSD would add £80 profit"
> "Upgrade to RTX 4070 for +£120 margin"

---

## 📊 What Happens After Saving

1. ✅ Build is created in your system
2. 🤖 LLM evaluates pricing (takes ~5-10 seconds)
3. 📈 You see profit forecast
4. 🚀 Auto-redirects to **Selling** page
5. 💰 Build is ready to list on eBay immediately

---

## 💡 Pro Tips

### Component Naming
✅ **Good:**
- "Intel Core i7-10700K"
- "RTX 3070 8GB"
- "32GB DDR4 3600MHz"

❌ **Bad:**
- "CPU"
- "graphics card"
- "memory"

### Market Price Checking
- Do this **before** you save (let it inform your costs)
- Check 2-3 components to validate your prices
- If many components show red deal scores, you overspent overall

### Condition Matters
- "New" = highest resale value but rare
- "Refurb" = good balance
- "Used" = lower resale but common

---

## 🔄 Workflow Integration

After adding your build:

1. System auto-evaluates with LLM
2. View the profit forecast
3. Click **"Go to Selling"** → moves to `/selling` page
4. Build appears in your "ready to sell" list
5. Generate title & description
6. Upload product photos
7. Hit SELL to publish on eBay

---

## 📲 What the LLM Knows

When evaluating your build, the AI considers:

✓ **Real market data** - Today's eBay/Amazon/Gumtree prices  
✓ **Component compatibility** - Warns if parts don't fit  
✓ **Demand trends** - Gaming PCs vs. workstations, seasonal changes  
✓ **Your pricing** - Compares what you paid to current market  
✓ **Upgrade paths** - Suggestions to maximize profit  
✓ **Seasonal factors** - Winter vs. summer demand  
✓ **Seller margins** - Accounts for platform fees (eBay, etc.)

---

## 🚨 Common Issues

### "Check Price" not working?
- Component name might be too vague
- Try: "Intel Core i7-10700K" instead of "Intel CPU"
- Give it 2-3 seconds after typing

### Profit seems low?
- You might have overpaid on components
- Check market prices with "Check Price" button
- Consider if upgrades would help

### Build won't save?
- Make sure all **required** components are filled in:
  - CPU, Motherboard, RAM, Storage, PSU
- Build name must not be empty

---

## ✅ Next Steps

1. **Go to `/add-build`** in your admin dashboard
2. **Enter your PC components** (the one you just bought!)
3. **Click "Check Price"** on 2-3 components to verify market rates
4. **Click "Save & Evaluate Build"** and wait for LLM assessment
5. **Review the profit forecast** - the AI will tell you if it's a good flip
6. **Move to Selling** to create the listing

Happy flipping! 🎯
