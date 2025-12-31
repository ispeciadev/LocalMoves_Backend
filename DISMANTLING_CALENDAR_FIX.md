# Dismantling/Reassembly & Calendar Pricing Fix

## Issues Identified

### 1. **Dismantling & Reassembly Costs Showing 0**

**Root Cause:** In your API response, `total_volume_m3: 0.0` and `item_details: []`

The dismantling and reassembly costs are calculated based on selected items:
```python
dismantling_cost = dismantling_volume_m3 * company_rates['disassembly_cost_per_m3']
reassembly_cost = reassembly_volume_m3 * company_rates['assembly_cost_per_m3']
```

Since no items are being passed in the API request, `dismantling_volume_m3` and `reassembly_volume_m3` are both **0**, resulting in costs of **0**.

**Solution:** Pass `selected_items` in your API request with actual item data.

**Example request:**
```json
{
  "pincode": "248002",
  "selected_items": {
    "Bedside Table": 50,
    "Bookcase Small": 340
  },
  "dismantle_items": {
    "Bedside Table": true
  },
  "distance_miles": 28.3,
  "include_dismantling": true,
  "include_reassembly": true,
  "...other fields"
}
```

---

### 2. **Calendar Pricing Showing "Calendar pricing unavailable" Error**

**Root Cause:** Import error in `search_companies_with_cost` function at line 2217

**The Problem:**
```python
# WRONG - Only imports timedelta, not the datetime class
from datetime import timedelta

# Later tries to use:
current_date = datetime.now().date()  # ❌ datetime is not defined!
```

**The Fix:**
```python
# CORRECT - Import both datetime class and timedelta
from datetime import datetime as datetime_class, timedelta

# Now use:
current_date = datetime_class.now().date()  # ✅ Works!
start_date = datetime_class.strptime(selected_move_date, "%Y-%m-%d").date()  # ✅ Works!
```

---

## Code Changes Made

### File: `company.py`

**Location:** Lines 2217-2221 (Calendar pricing section)

**Changed from:**
```python
from localmoves.api.calendar_pricing import calculate_final_price_for_date
from datetime import timedelta

base_price = company['exact_pricing']['final_total']
current_date = datetime.now().date()

# Start from selected_move_date or today
if selected_move_date:
    start_date = datetime.strptime(selected_move_date, "%Y-%m-%d").date()
```

**Changed to:**
```python
from localmoves.api.calendar_pricing import calculate_final_price_for_date
from datetime import datetime as datetime_class, timedelta

base_price = company['exact_pricing']['final_total']
current_date = datetime_class.now().date()

# Start from selected_move_date or today
if selected_move_date:
    start_date = datetime_class.strptime(selected_move_date, "%Y-%m-%d").date()
```

---

## How Calendar Pricing Works Now

Once calendar pricing loads successfully, it returns:

```json
{
  "calendar_pricing": {
    "base_price": 0.0,
    "next_7_days": [
      {
        "date": "2025-12-30",
        "day_of_week": "Tuesday",
        "price": 0.0,
        "notice_days": 0,
        "multipliers": {...},
        "color": "green",
        "uplift_percentage": 0.0,
        "reasons": ["Standard pricing"]
      },
      // ... 6 more days
    ],
    "cheapest_day": { "date": "2025-12-30", "price": 0.0, ... },
    "most_expensive_day": { "date": "2026-01-01", "price": 0.0, ... }
  }
}
```

The `cheapest_day` is the first price shown in the calendar list.

---

## Summary

| Issue | Cause | Fix |
|-------|-------|-----|
| Dismantling/Reassembly = 0 | No items in request | Send `selected_items` in API call |
| Calendar pricing error | Missing `datetime` import | Import `datetime as datetime_class` |

---

## Testing

To verify the fix works:

1. **Test with items:**
   ```bash
   POST /api/method/search_companies_with_cost
   {
     "pincode": "248002",
     "selected_items": {"Bedside Table": 50},
     "dismantle_items": {"Bedside Table": true},
     "distance_miles": 28.3,
     "include_dismantling": true,
     "include_reassembly": true,
     "selected_move_date": "2026-01-05"
   }
   ```

2. **Check response:**
   - ✅ `dismantling_cost` > 0
   - ✅ `reassembly_cost` > 0
   - ✅ `calendar_pricing` has `next_7_days` array (not error)
   - ✅ `calendar_pricing.cheapest_day` is populated

