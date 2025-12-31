# Frontend Fix Guide: Price Fluctuation Issue

**Document Version:** 1.0  
**Created:** December 30, 2025  
**Status:** Ready for Implementation

---

## Table of Contents
1. [Problem Statement](#problem-statement)
2. [Root Cause Analysis](#root-cause-analysis)
3. [Solution Overview](#solution-overview)
4. [Step-by-Step Implementation](#step-by-step-implementation)
5. [Code Examples](#code-examples)
6. [API Parameters](#api-parameters)
7. [Testing Checklist](#testing-checklist)
8. [Expected Results](#expected-results)

---

## Problem Statement

### Issue Description
Users experience significant price fluctuations when searching for moving companies and then refining their options.

**Example:**
- **First Search:** Blue Dart = **£8,449.34** (for Jan 8, 2026)
- **Refine Options:** User goes back to adjust items
- **Second Search:** Blue Dart = **£3,785.25** (completely different price)
- **Difference:** £4,664.09 (55% price drop!)

### Impact
- Users lose trust in pricing consistency
- Different prices shown for same move parameters
- Calendar shows incorrect base prices
- Confusing user experience

### Root Cause
When the user clicks "Refine Options" to go back and modify items, the following data is being **cleared/reset**:
- `selected_move_date` (e.g., "2026-01-08")
- `notice_period` (e.g., "within_2_weeks")
- `move_day` (e.g., "sun_to_thurs")

When the second search is executed, the API receives **NO date information**, so it defaults to today's date with default notice period settings, resulting in completely different pricing calculations.

---

## Root Cause Analysis

### How Backend Processes Pricing

The backend API (`search_companies_with_cost`) uses **three parameters to calculate final price**:

```
Final Price = Base Price × (notice_multiplier × day_multiplier × other_multipliers)
```

**Example for Blue Dart:**

| Parameter | First Search | Second Search |
|-----------|--------------|---------------|
| selected_move_date | 2026-01-08 | NULL (defaults to today) |
| notice_period | within_2_weeks (1.1x) | over_1_month (0.9x) |
| move_day | sun_to_thurs (1.0x) | default (1.0x) |
| Base inventory cost | £7,000 | £7,000 |
| **Final Price** | **£8,449** | **£3,785** |

### Why Calendar Shows Wrong Prices

The calendar uses `subtotal_before_date` (pure base) + applies multipliers for each date. If the base price sent is wrong, entire calendar is wrong.

---

## Solution Overview

### What to Fix

Preserve three key pieces of data across page navigation:

1. **selected_move_date** - The specific date user selected from calendar
2. **notice_period** - How far in advance the move is planned
3. **move_day** - Which day of week user prefers

### Where to Preserve

Use React state + browser storage (sessionStorage):

```
User selects date
    ↓
Store in state + sessionStorage
    ↓
User refines options
    ↓
Restore from sessionStorage
    ↓
Pass to API on second search
    ↓
✅ Same pricing
```

---

## Step-by-Step Implementation

### Step 1: Create State Variables

**File:** `RefineOptions.jsx` or your main search component

```javascript
import { useState, useEffect } from 'react';

export function RefineOptionsPage() {
  // Existing state
  const [selectedItems, setSelectedItems] = useState({});
  const [dismantleItems, setDismantleItems] = useState({});
  
  // ADD THESE NEW STATE VARIABLES
  const [selectedMoveDate, setSelectedMoveDate] = useState(null);
  const [noticePeriod, setNoticePeriod] = useState(null);
  const [moveDay, setMoveDay] = useState(null);
  
  return (
    // Your JSX here
  );
}
```

---

### Step 2: Restore from Storage on Mount

**Add this useEffect hook:**

```javascript
useEffect(() => {
  // On component mount, restore saved values from sessionStorage
  const savedDate = sessionStorage.getItem('selectedMoveDate');
  const savedNotice = sessionStorage.getItem('noticePeriod');
  const savedDay = sessionStorage.getItem('moveDay');
  
  if (savedDate) {
    setSelectedMoveDate(savedDate);
  }
  if (savedNotice) {
    setNoticePeriod(savedNotice);
  }
  if (savedDay) {
    setMoveDay(savedDay);
  }
  
  console.log('Restored from storage:', {
    date: savedDate,
    notice: savedNotice,
    day: savedDay
  });
}, []);
```

---

### Step 3: Save to Storage When Date Selected

**In your calendar date selection handler:**

```javascript
const handleDateSelect = (date) => {
  // Format date as YYYY-MM-DD
  const formattedDate = date.toISOString().split('T')[0];
  
  // Update state
  setSelectedMoveDate(formattedDate);
  
  // Save to sessionStorage
  sessionStorage.setItem('selectedMoveDate', formattedDate);
  
  console.log('Saved selected date:', formattedDate);
};
```

---

### Step 4: Save Notice Period & Move Day

**When these preferences are set:**

```javascript
const handleNoticeChange = (value) => {
  setNoticePeriod(value);
  sessionStorage.setItem('noticePeriod', value);
  console.log('Saved notice period:', value);
};

const handleMoveDayChange = (value) => {
  setMoveDay(value);
  sessionStorage.setItem('moveDay', value);
  console.log('Saved move day:', value);
};
```

---

### Step 5: Pass Values to API

**When calling search_companies_with_cost:**

```javascript
const searchCompanies = async () => {
  try {
    // Build payload with ALL required fields
    const payload = {
      // Existing fields
      pincode: pincode,
      selected_items: JSON.stringify(selectedItems),
      dismantle_items: JSON.stringify(dismantleItems),
      distance_miles: distanceMiles,
      property_type: propertyType,
      quantity: quantity,
      additional_spaces: JSON.stringify(additionalSpaces),
      
      // CRITICAL: Add these three fields
      selected_move_date: selectedMoveDate,  // ← Add this
      notice_period: noticePeriod,           // ← Add this
      move_day: moveDay,                     // ← Add this
      
      // Other fields
      include_packing: true,
      include_dismantling: true,
      include_reassembly: true,
      collection_parking: collectionParking,
      collection_parking_distance: collectionParkingDistance,
      collection_house_type: collectionHouseType,
      collection_internal_access: collectionInternalAccess,
      collection_floor_level: collectionFloorLevel,
      delivery_parking: deliveryParking,
      delivery_parking_distance: deliveryParkingDistance,
      delivery_house_type: deliveryHouseType,
      delivery_internal_access: deliveryInternalAccess,
      delivery_floor_level: deliveryFloorLevel,
    };
    
    // Call API
    const response = await frappe.call({
      method: 'localmoves.api.company.search_companies_with_cost',
      args: payload,
      callback: function(r) {
        if (r.message && r.message.success) {
          setCompanies(r.message.data);
        }
      }
    });
    
  } catch (error) {
    console.error('Search failed:', error);
  }
};
```

---

### Step 6: Fix "Refine Options" Button

**IMPORTANT: Don't clear the saved values!**

```javascript
// ❌ OLD CODE (DELETE THIS)
const handleRefineOptions = () => {
  setSelectedMoveDate(null);  // WRONG! Clears date
  setNoticePeriod(null);      // WRONG! Clears notice
  setMoveDay(null);           // WRONG! Clears move day
  navigate('/refine-options');
};

// ✅ NEW CODE (USE THIS)
const handleRefineOptions = () => {
  // Don't clear anything - keep the date and preferences!
  // Values are preserved in sessionStorage
  navigate('/refine-options');
};
```

---

### Step 7: Display Selected Values to User

**Show what date they selected so there's transparency:**

```javascript
{selectedMoveDate && (
  <div className="alert alert-info" style={{
    backgroundColor: '#e3f2fd',
    border: '1px solid #90caf9',
    borderRadius: '4px',
    padding: '12px',
    marginBottom: '16px',
    fontSize: '14px'
  }}>
    <strong>📅 Move Details:</strong>
    <ul style={{ marginTop: '8px', marginBottom: '0px' }}>
      <li>
        <strong>Date:</strong> {new Date(selectedMoveDate).toLocaleDateString('en-GB', {
          weekday: 'long',
          year: 'numeric',
          month: 'long',
          day: 'numeric'
        })}
      </li>
      <li>
        <strong>Notice Period:</strong> {noticePeriod ? noticePeriod.replace(/_/g, ' ') : 'Not specified'}
      </li>
      <li>
        <strong>Preferred Day:</strong> {moveDay ? moveDay.replace(/_/g, ' ') : 'Not specified'}
      </li>
    </ul>
    <small style={{ color: '#666', marginTop: '8px', display: 'block' }}>
      Prices are calculated for these selected parameters
    </small>
  </div>
)}
```

---

## Code Examples

### Complete Calendar Selection Handler

```javascript
/**
 * Handle calendar date selection
 * Saves to state + sessionStorage
 */
const handleCalendarDateClick = (date) => {
  // Format: YYYY-MM-DD
  const formattedDate = date.toISOString().split('T')[0];
  
  // Update state
  setSelectedMoveDate(formattedDate);
  
  // Save to sessionStorage for persistence
  sessionStorage.setItem('selectedMoveDate', formattedDate);
  
  // Log for debugging
  console.log('Date selected:', formattedDate);
  
  // Optional: Auto-trigger search or show confirmation
  setShowConfirmation(true);
};
```

### Complete Search Function

```javascript
/**
 * Search companies with all parameters including date
 */
const searchCompaniesWithPrice = async () => {
  if (!selectedMoveDate) {
    alert('Please select a move date first');
    return;
  }
  
  try {
    setIsLoading(true);
    
    const payload = {
      // Core parameters
      pincode,
      selected_items: JSON.stringify(selectedItems),
      dismantle_items: JSON.stringify(dismantleItems),
      distance_miles: parseFloat(distanceMiles),
      quantity,
      
      // DATE PARAMETERS (CRITICAL!)
      selected_move_date: selectedMoveDate,
      notice_period: noticePeriod,
      move_day: moveDay,
      
      // Service options
      include_packing: true,
      include_dismantling: true,
      include_reassembly: true,
      
      // Assessment parameters
      collection_parking,
      collection_parking_distance,
      collection_house_type,
      collection_internal_access,
      collection_floor_level,
      delivery_parking,
      delivery_parking_distance,
      delivery_house_type,
      delivery_internal_access,
      delivery_floor_level,
    };
    
    const response = await frappe.call({
      method: 'localmoves.api.company.search_companies_with_cost',
      args: payload,
      callback: function(r) {
        setIsLoading(false);
        
        if (r.message && r.message.success) {
          // Store companies
          setCompanies(r.message.data);
          
          // Log for verification
          console.log('Search results received:', {
            count: r.message.data.length,
            selectedDate: selectedMoveDate,
            noticePeriod,
            moveDay
          });
          
          // Navigate to results
          navigate('/filtered-providers');
        } else {
          alert('No companies found for your criteria');
        }
      },
      error: function(err) {
        setIsLoading(false);
        console.error('Search error:', err);
        alert('Error searching companies: ' + err.message);
      }
    });
    
  } catch (error) {
    setIsLoading(false);
    console.error('Unexpected error:', error);
  }
};
```

### Component Initialization

```javascript
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export function RefineOptionsComponent() {
  // State management
  const navigate = useNavigate();
  const [selectedItems, setSelectedItems] = useState({});
  const [dismantleItems, setDismantleItems] = useState({});
  const [selectedMoveDate, setSelectedMoveDate] = useState(null);
  const [noticePeriod, setNoticePeriod] = useState(null);
  const [moveDay, setMoveDay] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  
  // Restore saved values on mount
  useEffect(() => {
    const savedDate = sessionStorage.getItem('selectedMoveDate');
    const savedNotice = sessionStorage.getItem('noticePeriod');
    const savedDay = sessionStorage.getItem('moveDay');
    
    if (savedDate) setSelectedMoveDate(savedDate);
    if (savedNotice) setNoticePeriod(savedNotice);
    if (savedDay) setMoveDay(savedDay);
    
    console.log('✅ Restored values from sessionStorage');
  }, []);
  
  // Save whenever values change
  useEffect(() => {
    if (selectedMoveDate) {
      sessionStorage.setItem('selectedMoveDate', selectedMoveDate);
    }
  }, [selectedMoveDate]);
  
  useEffect(() => {
    if (noticePeriod) {
      sessionStorage.setItem('noticePeriod', noticePeriod);
    }
  }, [noticePeriod]);
  
  useEffect(() => {
    if (moveDay) {
      sessionStorage.setItem('moveDay', moveDay);
    }
  }, [moveDay]);
  
  return (
    <div className="refine-options">
      {/* Show selected parameters */}
      {selectedMoveDate && (
        <div className="selected-params">
          <h4>Selected Move Details</h4>
          <p>Date: {selectedMoveDate}</p>
          <p>Notice: {noticePeriod}</p>
          <p>Day: {moveDay}</p>
        </div>
      )}
      
      {/* Your refine form here */}
      
      {/* Search button */}
      <button 
        onClick={searchCompaniesWithPrice}
        disabled={isLoading}
      >
        {isLoading ? 'Searching...' : 'Search Companies'}
      </button>
    </div>
  );
}
```

---

## API Parameters

### Request Body Structure

**Endpoint:** `/api/method/localmoves.api.company.search_companies_with_cost`

**Method:** POST

**Required Parameters:**
```json
{
  "pincode": "176310",
  "selected_items": "{\"Bedroom-Bedside Table\": 1, \"Bedroom-Bookcase Large\": 0}",
  "dismantle_items": "{\"Bedroom-Bedside Table\": true}",
  "distance_miles": "330",
  "quantity": "half_contents",
  "property_type": "flat",
  "property_size": "2_bed"
}
```

**CRITICAL - Date Parameters (must add these):**
```json
{
  "selected_move_date": "2026-01-08",
  "notice_period": "within_2_weeks",
  "move_day": "sun_to_thurs"
}
```

**Optional - Service Selection:**
```json
{
  "include_packing": true,
  "include_dismantling": true,
  "include_reassembly": true
}
```

**Optional - Collection Assessment:**
```json
{
  "collection_parking": "driveway",
  "collection_parking_distance": "less_than_10m",
  "collection_house_type": "house_ground_and_1st",
  "collection_internal_access": "stairs_only",
  "collection_floor_level": "ground_floor"
}
```

**Optional - Delivery Assessment:**
```json
{
  "delivery_parking": "driveway",
  "delivery_parking_distance": "less_than_10m",
  "delivery_house_type": "house_ground_and_1st",
  "delivery_internal_access": "stairs_only",
  "delivery_floor_level": "ground_floor"
}
```

### Valid Values Reference

**notice_period options:**
- `same_day`
- `within_1_day`
- `within_2_days`
- `within_3_days`
- `within_a_week`
- `within_2_weeks`
- `within_a_month`
- `over_1_month`
- `flexible`

**move_day options:**
- `sun_to_thurs` (save 15%)
- `fri_to_sat` (standard rate)

**quantity options:**
- `some_things`
- `half_contents`
- `three_quarter`
- `everything`

**parking options:**
- `driveway`
- `roadside`

**parking_distance options:**
- `less_than_10m`
- `10_to_20m`
- `over_20m`

**house_type options:**
- `house_ground_and_1st`
- `bungalow_ground`
- `townhouse_ground_1st_2nd`

**internal_access options:**
- `stairs_only`
- `lift_access`

**floor_level options:**
- `ground_floor`
- `1st_floor`
- `2nd_floor`
- `3rd_floor_plus`

---

## Testing Checklist

### Pre-Implementation Testing
- [ ] Verify current behavior (price changes on refine)
- [ ] Take screenshot of first search price
- [ ] Take screenshot of second search price
- [ ] Note the price difference

### Implementation Testing

#### Test 1: Basic Date Persistence
- [ ] User selects date "2026-01-08" from calendar
- [ ] User clicks "Refine Options" button
- [ ] Return to search page
- [ ] Verify `sessionStorage.getItem('selectedMoveDate')` = "2026-01-08"
- [ ] Check console shows "Restored values from sessionStorage"

#### Test 2: Price Consistency
- [ ] First search with date "2026-01-08": Note price (should be £8,449)
- [ ] Refine options, change items
- [ ] Search again: Price should remain **same or very similar**
- [ ] Check calendar shows correct base price

#### Test 3: Notice Period Preservation
- [ ] Select "within_2_weeks" notice period
- [ ] Refine options
- [ ] Search again
- [ ] Verify in browser console: `sessionStorage.getItem('noticePeriod')` = "within_2_weeks"

#### Test 4: Move Day Preservation
- [ ] Select "sun_to_thurs" move day
- [ ] Refine options
- [ ] Search again
- [ ] Verify in browser console: `sessionStorage.getItem('moveDay')` = "sun_to_thurs"

#### Test 5: Calendar Pricing Alignment
- [ ] Search with date "2026-01-08"
- [ ] Note company price: £8,449.34
- [ ] Check calendar "base_price": should be £8,449.34
- [ ] Selected date (Jan 8) in calendar should show £8,449.34
- [ ] Other dates should adjust up/down from this base

#### Test 6: Multiple Refinements
- [ ] Refine options 3-4 times
- [ ] Check each time: prices remain consistent
- [ ] Verify sessionStorage still has correct values after each refine

#### Test 7: Browser Refresh
- [ ] Select date and search
- [ ] Refresh browser (F5)
- [ ] Verify selectedMoveDate, noticePeriod, moveDay are restored
- [ ] Price should be same after refresh

#### Test 8: New Search (Clear Values)
- [ ] After successful search, user starts NEW search
- [ ] Clear sessionStorage before starting new search
- [ ] New search should use new date, not old date

### Post-Implementation Verification
- [ ] First search: £8,449 (Blue Dart, Jan 8)
- [ ] Refine items
- [ ] Second search: £8,449 (Blue Dart, Jan 8) ✅ SAME PRICE
- [ ] Calendar base_price: £8,449 ✅ MATCHES
- [ ] User can see selected date in UI ✅ TRANSPARENT

---

## Expected Results

### Before Fix
```
❌ First Search
  Date: 2026-01-08
  Notice: within_2_weeks
  Blue Dart Price: £8,449.34

❌ Refine & Search Again
  Date: NULL (defaults to today)
  Notice: over_1_month (default)
  Blue Dart Price: £3,785.25

❌ Price difference: £4,664 (55% drop) 🔴
```

### After Fix
```
✅ First Search
  Date: 2026-01-08
  Notice: within_2_weeks
  Blue Dart Price: £8,449.34
  Calendar base: £8,449.34

✅ Refine & Search Again
  Date: 2026-01-08 (PRESERVED)
  Notice: within_2_weeks (PRESERVED)
  Blue Dart Price: £8,449.34
  Calendar base: £8,449.34

✅ Price difference: £0 (100% consistent) 🟢
```

---

## Debugging Tips

### Enable Console Logging

Add these logs to track the flow:

```javascript
// When saving
console.log('💾 Saved to sessionStorage:', {
  date: selectedMoveDate,
  notice: noticePeriod,
  day: moveDay
});

// When restoring
console.log('📂 Restored from sessionStorage:', {
  date: savedDate,
  notice: savedNotice,
  day: savedDay
});

// Before API call
console.log('🔍 Sending to API:', {
  selected_move_date: selectedMoveDate,
  notice_period: noticePeriod,
  move_day: moveDay
});

// After API response
console.log('📊 API Response received:', {
  companies: r.message.data.length,
  firstCompanyPrice: r.message.data[0]?.exact_pricing?.final_total,
  calendarBase: r.message.data[0]?.calendar_pricing?.base_price
});
```

### Check sessionStorage in Browser

Open browser DevTools (F12):
```javascript
// Check what's stored
sessionStorage.getItem('selectedMoveDate')  // Should print "2026-01-08"
sessionStorage.getItem('noticePeriod')      // Should print "within_2_weeks"
sessionStorage.getItem('moveDay')           // Should print "sun_to_thurs"

// Clear if needed
sessionStorage.clear()
```

### Verify API Payload

In browser Network tab:
1. Open DevTools → Network tab
2. Click "Search Companies" button
3. Find `search_companies_with_cost` request
4. Check "Payload" tab
5. Verify these three fields are present:
   - `selected_move_date: "2026-01-08"`
   - `notice_period: "within_2_weeks"`
   - `move_day: "sun_to_thurs"`

---

## Common Issues & Solutions

### Issue 1: Values Not Persisting After Refine

**Problem:** sessionStorage is empty after navigate

**Solution:** 
- Confirm useEffect hook for saving is added
- Check useEffect dependencies are correct
- Verify sessionStorage.setItem() is being called (check console logs)

**Code Check:**
```javascript
useEffect(() => {
  if (selectedMoveDate) {
    sessionStorage.setItem('selectedMoveDate', selectedMoveDate);
    console.log('✅ Saved:', selectedMoveDate);
  }
}, [selectedMoveDate]);  // ← Important: must have dependency
```

### Issue 2: Calendar Showing Wrong Base Price

**Problem:** Calendar base_price doesn't match company price

**Solution:**
- Verify selected_move_date is being sent to API
- Check API response includes `calendar_pricing.base_price`
- Confirm backend is using correct base calculation

**Verify in API Response:**
```javascript
console.log(response.data[0].exact_pricing.final_total);      // Should be £8,449
console.log(response.data[0].calendar_pricing.base_price);    // Should be £8,449
```

### Issue 3: Price Still Changes on Refine

**Problem:** Even with date preserved, price changes

**Solution:**
- Check if API is receiving the date parameter
- Verify date format is correct: "YYYY-MM-DD"
- Check notice_period and move_day are also being sent

**Debug:**
```javascript
// Before API call, log the payload
console.log('Payload being sent:', payload);
// Then check API received it (look in Network tab)
```

### Issue 4: sessionStorage Persists Across Different Users

**Problem:** User A's date persists when User B logs in

**Solution:**
- Clear sessionStorage on logout
- Clear before starting new search

**Add to Logout:**
```javascript
const handleLogout = () => {
  sessionStorage.removeItem('selectedMoveDate');
  sessionStorage.removeItem('noticePeriod');
  sessionStorage.removeItem('moveDay');
  // ... other logout logic
};
```

---

## Summary

| Item | Before | After |
|------|--------|-------|
| Price on first search | £8,449 | £8,449 |
| Price after refine | £3,785 ❌ | £8,449 ✅ |
| Calendar base price | £7,231 (wrong) | £8,449 (correct) |
| User experience | Confusing | Transparent |
| Data persistence | Lost | Preserved |

---

## Questions?

If implementation questions arise:
1. Check the console logs for what data is being stored/sent
2. Verify browser sessionStorage in DevTools
3. Check API Network request payload in DevTools
4. Review the complete code examples in this document

**All backend changes are already complete.** This is purely a frontend preservation issue.

---

**End of Document**
