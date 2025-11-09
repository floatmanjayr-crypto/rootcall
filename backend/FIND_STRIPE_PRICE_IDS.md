# ��� How to Find Stripe Price IDs - Step by Step

## Step 1: Go to Stripe Dashboard
��� https://dashboard.stripe.com/test/products

## Step 2: Create Your First Product

### Click "➕ Add Product" button (top right)

Fill in:
- **Name:** Basic Protection
- **Description:** Spam & spoof blocking with caller ID screening
- **Pricing Model:** ✅ Standard pricing
- **Price:** $34.99
- **Billing period:** ✅ Monthly (Recurring)
- **Currency:** USD

Click **"Save Product"**

## Step 3: Find the Price ID

After saving, you'll see your product page.

Look for the **"Pricing"** section. You'll see something like:
```
┌─────────────────────────────────────────┐
│ Pricing                                 │
├─────────────────────────────────────────┤
│ $34.99 / month                         │
│ price_1AbCdEfGhIjKlMnOp               │  ← THIS IS YOUR PRICE ID!
│                                         │
│ [API ID] [Copy]                        │
└─────────────────────────────────────────┘
```

**Click the [Copy] button** next to the Price ID!

It will look like: `price_1AbCdEfGhIjKlMnOp` or `price_xxxxxxxxxxxxx`

## Step 4: Add to .env File

Open your `.env` file and add:
```env
STRIPE_BASIC_PRICE_ID=price_1AbCdEfGhIjKlMnOp
```

## Step 5: Repeat for Other Plans

### Smart AI Screening ($69.99/month):
1. Click "➕ Add Product"
2. Name: Smart AI Screening
3. Price: $69.99/month
4. Save and copy Price ID
5. Add to .env: `STRIPE_SMART_PRICE_ID=price_xxxxxxxxx`

### Premium Family Shield ($124.99/month):
1. Click "➕ Add Product"
2. Name: Premium Family Shield
3. Price: $124.99/month
4. Save and copy Price ID
5. Add to .env: `STRIPE_PREMIUM_PRICE_ID=price_xxxxxxxxx`

## ��� Visual Guide
```
Stripe Dashboard
├── Products (left sidebar)
    ├── Click "Add Product"
    ├── Fill in product details
    ├── Set price and billing
    ├── Click "Save"
    └── ��� COPY THE PRICE ID FROM HERE!
```

## ✅ Your Final .env Should Look Like:
```env
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_51AbCdEfGhIjKlMnOp1234567890
STRIPE_BASIC_PRICE_ID=price_1Basic123456789
STRIPE_SMART_PRICE_ID=price_1Smart123456789
STRIPE_PREMIUM_PRICE_ID=price_1Premium123456789
```

## ��� Quick Test

After adding all Price IDs, test the API:
```bash
curl http://localhost:8000/api/payments/plans
```

You should see your plans with price_ids!

## ⚠️ Common Issues

**Issue:** "Invalid price ID"
**Fix:** Make sure you copied the FULL price ID including `price_`

**Issue:** "No such price"
**Fix:** Make sure you're in TEST mode and using test keys

**Issue:** Can't find Price ID
**Fix:** 
1. Go to Products
2. Click on the product name
3. Scroll to "Pricing" section
4. The Price ID is there!

## ��� Video Tutorial Alternative

If you prefer video:
��� https://www.youtube.com/results?search_query=stripe+price+id+tutorial

## Need More Help?

Run this command to see your current setup:
```bash
cat .env | grep STRIPE
```

This will show you what's configured!
