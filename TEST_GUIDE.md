# Quick Test Guide - Dismantling, Reassembly & Calendar Pricing

## What Was Wrong

### Before Fix ❌
```json
{
  "dismantling_cost": 0,
  "reassembly_cost": 0,
  "volumes_used": {
    "dismantling_volume_m3": 0,
    "reassembly_volume_m3": 0
  },
  "calendar_pricing": {
    "error": "Calendar pricing unavailable"
  }
}
```

### After Fix ✅
```json
{
  "dismantling_cost": 1225.0,
  "reassembly_cost": 2450.0,
  "volumes_used": {
    "dismantling_volume_m3": 50.0,
    "reassembly_volume_m3": 50.0
  },
  "calendar_pricing": {
    "base_price": 26317.64,
    "next_7_days": [
      {
        "date": "2026-01-05",
        "price": 34212.93,
        "color": "red"
      },
      ...
    ],
    "cheapest_day": { "date": "2026-01-06", "price": 34212.93 }
  }
}
```

---

## Test Case 1: With Dismantling Items

**Request:**
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
  "include_packing": true,
  "include_dismantling": true,
  "include_reassembly": true,
  "selected_move_date": "2026-01-05",
  "property_type": "house",
  "collection_parking": "driveway",
  "collection_parking_distance": "less_than_10m",
  "delivery_parking": "driveway",
  "delivery_parking_distance": "less_than_10m"
}
```

**Expected Results:**
- ✅ `dismantling_cost` > 0 (based on dismantled items)
- ✅ `reassembly_cost` > 0 (same as dismantling)
- ✅ `volumes_used.dismantling_volume_m3` = volume of Bedside Table × 50
- ✅ `calendar_pricing.next_7_days` = array of 7 days
- ✅ `calendar_pricing.cheapest_day` = object with cheapest date
- ✅ No "Calendar pricing unavailable" error

---

## Test Case 2: Without Dismantling Items

**Request:**
```json
{
  "pincode": "248002",
  "selected_items": {
    "Bedside Table": 50,
    "Bookcase Small": 340
  },
  "dismantle_items": {},
  "distance_miles": 28.3,
  "include_packing": true,
  "include_dismantling": false,
  "include_reassembly": false,
  "selected_move_date": "2026-01-05"
}
```

**Expected Results:**
- ✅ `dismantling_cost` = 0 (no items marked for dismantling)
- ✅ `reassembly_cost` = 0 (no items marked for dismantling)
- ✅ `volumes_used.dismantling_volume_m3` = 0
- ✅ `volumes_used.reassembly_volume_m3` = 0
- ✅ Calendar pricing still works (no error)

---

## Test Case 3: Calendar Pricing Specifics

The calendar pricing now:
1. **Calculates for 7 days** starting from `selected_move_date`
2. **Applies multipliers** based on:
   - Notice period (days until move)
   - Day of week (Friday/Saturday = +15%)
   - Bank holidays (if applicable)
   - School holidays (if applicable)
   - Last Friday of month
   - Demand multiplier

3. **Returns pricing data** with:
   - `date`: The date being quoted for
   - `price`: Final price with all multipliers
   - `multipliers`: All applied multipliers
   - `color`: Green (cheap), Amber (medium), Red (expensive)
   - `reasons`: Why the price is high/low

---

## Breakdown: Where Costs Come From

### Dismantling Cost Formula
```
dismantling_cost = dismantling_volume_m3 × disassembly_cost_per_m3
```

Where:
- `dismantling_volume_m3` = Sum of volumes of items marked for dismantling
- `disassembly_cost_per_m3` = Company's disassembly rate per m³ (from Moving Inventory Item)

**Example:**
- Bedside Table volume = 1.0 m³
- Quantity = 50
- Marked for dismantling? YES
- Dismantling volume = 50 m³
- Company disassembly rate = £24.50/m³
- **Dismantling cost = 50 × £24.50 = £1,225**

### Reassembly Cost Formula
```
reassembly_cost = reassembly_volume_m3 × assembly_cost_per_m3
```

Same as dismantling, but uses assembly rate instead.

**Example:**
- Same 50 m³ needs reassembly
- Company assembly rate = £49.00/m³
- **Reassembly cost = 50 × £49.00 = £2,450**

---

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Dismantling = 0 | Items not marked for dismantling | Add to `dismantle_items` |
| Calendar = error | Missing `selected_move_date` | Provide a valid date |
| Calendar = empty array | Date parsing error | Use `YYYY-MM-DD` format |
| Wrong volume | Wrong item name | Check exact name in database |
| Assembly too high | Company has expensive assembly rate | Try different company |

---

## API Response Structure - Full Example

```json
{
  "success": true,
  "count": 24,
  "data": [
    {
      "name": "Company Name",
      "company_name": "Company Name",
      "exact_pricing": {
        "total_volume_m3": 185.0,
        "distance_miles": 28.3,
        "inventory_cost": 5550.0,
        "mileage_cost": 1402.92,
        "packing_cost": 1942.5,
        "dismantling_cost": 1225.0,
        "reassembly_cost": 2450.0,
        "subtotal_before_date": 12570.42,
        "move_date_multiplier": 2.1,
        "final_total": 26397.88,
        "breakdown": {
          "inventory": 5550.0,
          "mileage": 1402.92,
          "packing": 1942.5,
          "dismantling": 1225.0,
          "reassembly": 2450.0,
          "date_adjustment": 13827.46
        }
      },
      "calendar_pricing": {
        "base_price": 26397.88,
        "next_7_days": [
          {
            "date": "2026-01-05",
            "day_of_week": "Monday",
            "price": 34292.35,
            "notice_days": 6,
            "multipliers": {
              "notice_period": 1.2,
              "day_of_week": 1.0,
              "bank_holiday": 1.0,
              "school_holiday": 1.0,
              "last_friday": 1.0,
              "demand": 1.15,
              "total": 1.38
            },
            "color": "red",
            "uplift_percentage": 30.0,
            "reasons": [
              "Within a Week - +20%",
              "High Demand (8 bookings) - +15%"
            ]
          },
          ...more days...
        ],
        "cheapest_day": {...},
        "most_expensive_day": {...}
      }
    }
  ]
}
```

