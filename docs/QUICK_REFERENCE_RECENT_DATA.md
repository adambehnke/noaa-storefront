# Quick Reference: Recent Data Examples

## 🚀 Quick Start

### View All Endpoints in a Pond
**Double-click** any data pond in the sidebar
- Example: Double-click "Atmospheric" to see all 8 weather endpoints
- Shows endpoint details, data types, and action buttons

### View Recent Ingested Data
**Click the green "Recent" button** next to any endpoint
- Located in the "Endpoints & Services" section
- Shows the most recently ingested data sample
- No live API call required

### Query Live Data
**Click the blue "Query" button** next to any endpoint
- Fetches fresh data directly from NOAA APIs
- Use when you need real-time information

---

## 🎯 Three Ways to Explore Data

### 1️⃣ Double-Click Method
```
Sidebar → Double-click "Oceanic" → See all tide/current endpoints
```
**Best for**: Exploring what's available in a pond

### 2️⃣ Recent Button Method
```
Sidebar → Endpoints & Services → Find endpoint → Click 🟢 Recent
```
**Best for**: Checking latest ingested data quickly

### 3️⃣ Query Button Method
```
Sidebar → Endpoints & Services → Find endpoint → Click 🔵 Query
```
**Best for**: Getting real-time data from source

---

## 📊 What You'll See

### When You Double-Click a Pond
- ✅ Pond statistics (files, size, last update)
- ✅ Complete list of all endpoints
- ✅ Data type descriptions
- ✅ Layer breakdown (Bronze/Silver/Gold)
- ✅ Action buttons for each endpoint

### When You Click "Recent"
- ✅ Latest ingestion timestamp
- ✅ Sample of actual data
- ✅ Storage location info
- ✅ File counts and sizes

---

## 🌊 Data Ponds & Endpoint Counts

| Pond | Endpoints | Data Sources |
|------|-----------|--------------|
| ☁️ Atmospheric | 8 | NWS (Weather) |
| 🌊 Oceanic | 8 | CO-OPS (Tides) |
| 🛟 Buoy | 5 | NDBC (Marine) |
| 📈 Climate | 7 | CDO (Historical) |
| 🗺️ Spatial | 2 | NEXRAD/GOES |
| ⛰️ Terrestrial | 3 | USGS (Rivers) |

**Total**: 33+ active endpoints

---

## 💡 Pro Tips

### Tip 1: Double-Click for Discovery
When you're not sure what data is available, double-click the pond first

### Tip 2: Recent vs. Query
- Use **Recent** when exploring (faster, no API limits)
- Use **Query** when you need live data (slower, rate limited)

### Tip 3: Check Timestamps
Look for "X minutes ago" to see how fresh the data is

### Tip 4: Layer Information
Bronze layer shows raw ingested data as it came from the API

### Tip 5: Keyboard Users
Press Tab to navigate between endpoints and buttons

---

## 🎨 Button Colors

| Color | Button | Purpose |
|-------|--------|---------|
| 🔵 Blue | Query | Live API call |
| 🟢 Green | Recent | Cached data |

---

## 📍 Example Use Cases

### Use Case 1: "What weather alerts are being collected?"
1. Double-click "Atmospheric" pond
2. Find "Active Alerts" endpoint
3. Click 🟢 Recent
4. View latest alert data sample

### Use Case 2: "Show me current tide data"
1. Expand "Endpoints & Services"
2. Find "Oceanic → Water Level"
3. Click 🔵 Query for live data
4. OR click 🟢 Recent for latest ingested

### Use Case 3: "What buoy data do we have?"
1. Double-click "Buoy" pond
2. Review all 5 buoy endpoints
3. Check timestamps and file counts
4. Click actions as needed

---

## ❓ Common Questions

**Q: What's the difference between Recent and Query?**
A: Recent shows cached data from the Data Lake. Query fetches fresh data from NOAA.

**Q: How old is "recent" data?**
A: Usually 3-30 minutes, depending on the pond's ingestion schedule.

**Q: Why would I use Recent instead of Query?**
A: It's faster, doesn't hit API rate limits, and good for exploring data structure.

**Q: Can I see all endpoints at once?**
A: Yes! Double-click "Federated" or any specific pond.

**Q: What if Recent shows an error?**
A: The endpoint may not have data yet. Try Query instead.

---

## 🔢 Cheat Sheet

| What You Want | How To Do It |
|---------------|--------------|
| Explore pond data | Double-click pond name |
| See recent example | Click 🟢 Recent button |
| Get live data | Click 🔵 Query button |
| View all endpoints | Double-click any pond |
| Check data freshness | Look for timestamp |
| See file counts | Double-click pond |
| View layers | Scroll to bottom of pond view |

---

## ⌨️ Keyboard Shortcuts

- **Tab** - Navigate between elements
- **Enter** - Activate focused button
- **Double-click** - Open pond details
- **Esc** - Close modals (if applicable)

---

## 📱 Works On

- ✅ Desktop (Chrome, Firefox, Safari, Edge)
- ✅ Tablet (iOS, Android)
- ✅ Mobile (responsive touch interface)

---

## 🆘 Need Help?

**Not seeing data?**
→ Check if the pond has been ingested (look for timestamps)

**Buttons not working?**
→ Hard refresh your browser (Ctrl+Shift+R or Cmd+Shift+R)

**Want more details?**
→ See `RECENT_DATA_EXAMPLES_FEATURE.md` for full documentation

---

**Version**: 1.0  
**Updated**: December 11, 2024  
**Status**: ✅ Active