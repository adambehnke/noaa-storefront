# Recent Data Examples Feature

## Overview

This feature enhances the NOAA Data Lake Storefront by allowing users to easily view the most recent ingested data examples from all endpoints across all data ponds. This provides transparency into what data is being collected and allows users to quickly inspect actual data samples without having to query the live APIs.

## Features Added

### 1. Double-Click Pond to View All Endpoints

**How to Use:**
- Double-click any data pond in the sidebar (Atmospheric, Oceanic, Buoy, Climate, Spatial, or Terrestrial)
- A comprehensive view will display showing:
  - Pond statistics (total files, size, last update time)
  - All active endpoints for that pond
  - Data type descriptions for each endpoint
  - Quick action buttons to query live data or view recent ingested data
  - Layer breakdown (Bronze, Silver, Gold) with file counts and sizes

**What You'll See:**
- Detailed information about each endpoint including:
  - Endpoint name and service
  - API path/URL
  - Description of the data type being collected
  - Recent ingestion timestamp
  - Action buttons for interaction

### 2. "Recent" Button for Each Endpoint

**How to Use:**
- Expand the "Endpoints & Services" section in the sidebar
- Each endpoint now has two action buttons:
  - **Query** (blue) - Fetches live data directly from NOAA API
  - **Recent** (green) - Shows the most recently ingested data from the Data Lake

**What the "Recent" Button Shows:**
- The most recent example of data ingested from that specific endpoint
- Timestamp of when the data was ingested
- Total file count for that endpoint
- Latest ingestion time with "minutes ago" indicator
- Bronze layer S3 path information
- Actual data sample preview

### 3. Enhanced Endpoint Panel

The endpoint panel now provides:
- Visual separation between "Query Live" and "View Recent" actions
- Clickable endpoint items with hover effects
- Service badges and token requirement indicators
- Total endpoint count across all ponds

## User Interface Enhancements

### Sidebar Updates
- Added helpful hint: "Double-click a pond to view recent data examples"
- Improved visibility of the tip with icon and italic styling
- Better visual hierarchy for pond selection instructions

### Endpoint Items
- Each endpoint now displays two clickable actions side by side:
  - 🔵 **Query** - Direct API query
  - 🟢 **Recent** - Recent ingested data
- Prevents accidental clicks by properly handling event propagation

## Technical Implementation

### New Functions

#### `showPondDataExamples(pondName)`
Displays comprehensive information about all endpoints in a specific pond:
- Fetches pond metadata from state
- Displays pond statistics and layer information
- Lists all endpoints with detailed descriptions
- Provides action buttons for each endpoint
- Shows customized data type descriptions based on pond and endpoint type

**Parameters:**
- `pondName` (string) - Name of the pond to display (e.g., "atmospheric", "oceanic")

#### `fetchRecentEndpointData(pond, service, endpointName)`
Retrieves and displays the most recent ingested data for a specific endpoint:
- Queries the backend API for recent data samples
- Displays ingestion timestamps and freshness
- Shows Bronze layer storage information
- Provides data preview with formatted output

**Parameters:**
- `pond` (string) - Pond name
- `service` (string) - Service identifier (e.g., "NWS", "COOPS", "NDBC")
- `endpointName` (string) - Name of the endpoint

### Event Handlers

1. **Double-click handler** on pond options:
   ```javascript
   pondOption.addEventListener('dblclick', () => {
     const pond = pondOption.dataset.pond;
     if (pond !== 'all') {
       showPondDataExamples(pond);
     }
   });
   ```

2. **Click handlers** for endpoint action buttons:
   - `.endpoint-query-btn` - Triggers live API query
   - `.endpoint-recent-btn` - Fetches recent ingested data

### Data Flow

1. **User Action** → Double-click pond or click "Recent" button
2. **Frontend** → Calls appropriate function (`showPondDataExamples` or `fetchRecentEndpointData`)
3. **API Request** → Queries backend for data (if needed)
4. **Data Processing** → Formats and enriches data with metadata
5. **Display** → Shows formatted information in chat interface

## Data Pond Endpoint Catalog

### Atmospheric Pond (NWS)
- Active Alerts - Weather warnings and advisories
- Point Forecasts - Location-specific weather forecasts
- Hourly Forecasts - Hour-by-hour weather predictions
- Observations - Current weather station readings
- Radar Stations - Available radar facilities
- Zone Forecasts - Regional forecast zones
- Products - Weather products and bulletins
- Glossary - Weather terminology

### Oceanic Pond (CO-OPS)
- Water Level - Real-time tide gauge measurements
- Predictions - Tide predictions
- Currents - Ocean current data
- Air Temperature - Coastal air temperature
- Water Temperature - Sea surface temperature
- Wind - Coastal wind observations
- Air Pressure - Barometric pressure readings
- Datums - Tidal datum information

### Buoy Pond (NDBC)
- Standard Met Data - Core meteorological observations
- Spectral Wave Data - Wave frequency analysis
- Ocean Data - Additional ocean parameters
- Active Stations - Currently reporting buoys
- Station Metadata - Buoy location and specifications

### Climate Pond (CDO)
- Datasets - Available climate datasets
- Data Categories - Climate data classifications
- Data Types - Specific measurement types
- Location Categories - Geographic groupings
- Locations - Specific geographic areas
- Stations - Weather station information
- Data - Historical climate records

### Spatial Pond
- Radar Products - NEXRAD radar imagery metadata
- Satellite Imagery - GOES satellite products

### Terrestrial Pond (USGS)
- Instantaneous Values - Real-time stream measurements
- Daily Values - Daily aggregated stream data
- Site Info - River gauge station details

## Benefits

1. **Transparency** - Users can see exactly what data is being ingested
2. **Data Discovery** - Easy exploration of available data types
3. **Quality Assurance** - Quick verification of data freshness and format
4. **User Guidance** - Clear descriptions help users understand data sources
5. **Efficiency** - No need to query live APIs just to see what data looks like
6. **Layer Visibility** - Shows medallion architecture (Bronze/Silver/Gold) status

## Usage Examples

### Example 1: View All Atmospheric Endpoints
1. Locate "Atmospheric" pond in the sidebar
2. Double-click on "Atmospheric"
3. Review all 8 endpoints with descriptions
4. Click "Query Live" on "Active Alerts" to see current weather alerts
5. Click "View Recent" to see the most recently ingested alert data

### Example 2: Check Recent Buoy Data
1. Expand "Endpoints & Services" section
2. Find "Buoy" pond section
3. Locate "Standard Met Data" endpoint
4. Click the green "Recent" button
5. View the most recent buoy observations ingested

### Example 3: Explore Data Lake Metrics
1. Double-click "Oceanic" pond
2. Review pond statistics (total files, size, last update)
3. See layer breakdown for Bronze, Silver, and Gold
4. Check which endpoints have been updated recently

## Future Enhancements

Potential improvements for this feature:

- [ ] Add sample data preview directly in the endpoint list
- [ ] Show data freshness indicators (excellent/good/stale)
- [ ] Display ingestion frequency for each endpoint
- [ ] Add data quality metrics (completeness, validation status)
- [ ] Implement endpoint health monitoring
- [ ] Add historical ingestion charts
- [ ] Enable data export from recent examples
- [ ] Add filtering and search for endpoints
- [ ] Show endpoint dependencies and relationships
- [ ] Add comparison view between live and ingested data

## Troubleshooting

### "Failed to Fetch Recent Data" Error
- **Cause**: Backend API may be unavailable or endpoint has no recent data
- **Solution**: Try clicking "Query Live" instead, or check with system administrator

### No Data Displayed
- **Cause**: Endpoint may not have been ingested yet
- **Solution**: Check the Data Lake Metrics to see ingestion status

### Slow Loading
- **Cause**: Large data samples may take time to load
- **Solution**: The system will show a loading indicator; please wait

## Technical Notes

- Recent data is fetched from the Bronze layer (raw ingested data)
- Data freshness is calculated in real-time based on latest ingestion timestamp
- The feature respects the existing medallion architecture (Bronze → Silver → Gold)
- All timestamps are displayed in the user's local timezone
- Data samples are limited to prevent overwhelming the UI

## Related Documentation

- `DASHBOARD_PONDS_FIX.md` - Dashboard improvements
- `SYSTEM_ENHANCEMENTS_DEC11.md` - Overall system enhancements
- `INGESTION_STATUS_REPORT.md` - Ingestion system status
- `pond_metadata.json` - Pond metadata structure

## Version History

- **v1.0** (December 2024) - Initial release
  - Double-click pond feature
  - Recent data button for endpoints
  - Enhanced endpoint panel
  - Comprehensive data type descriptions

---

**Feature Status**: ✅ Active and Deployed

**Maintained By**: NOAA Data Lake Team

**Last Updated**: December 11, 2024