# NOAA Federated Data Lake - Data Catalog

> **Version:** 1.0  
> **Last Updated:** November 2024  
> **Purpose:** Comprehensive catalog of all data sources, schemas, and query patterns

## 📚 Table of Contents

- [Overview](#overview)
- [Data Ponds](#data-ponds)
- [Endpoint Catalog](#endpoint-catalog)
- [Schema Reference](#schema-reference)
- [Query Patterns](#query-patterns)
- [Cross-Pond Relationships](#cross-pond-relationships)
- [Use Cases](#use-cases)

---

## 🌊 Overview

The NOAA Federated Data Lake integrates **25+ NOAA API endpoints** across **6 specialized data ponds**, providing comprehensive environmental and meteorological data coverage across the United States.

### Data Coverage Summary

| Pond | Endpoints | Update Frequency | Stations/Locations | Data Types |
|------|-----------|------------------|-------------------|------------|
| Oceanic | 5+ | 15 minutes | 50+ buoys, 200+ tide stations | Wave height, water temp, currents, tides |
| Atmospheric | 8+ | 15 minutes | 50+ cities, national alerts | Forecasts, alerts, observations |
| Climate | 4+ | 1 hour | 100+ climate stations | Historical temps, precipitation, normals |
| Spatial | 2+ | 30 minutes | National coverage | Radar, satellite metadata |
| Terrestrial | 2+ | 30 minutes | 1000+ river gauges | Stream flow, river levels |
| Buoy | 3+ | 15 minutes | 150+ offshore buoys | Real-time marine conditions |

### Total Data Volume

- **Endpoints:** 25+
- **Daily Ingestions:** 2,000+
- **Monthly Data Points:** 1M+
- **Storage (Bronze):** ~5GB/month
- **Storage (Gold):** ~2GB/month

---

## 🗂️ Data Ponds

### 1. 🌊 Oceanic Pond

**Purpose:** Real-time and historical ocean and coastal data

**Data Sources:**
- NOAA National Data Buoy Center (NDBC)
- CO-OPS Tides and Currents API
- Ocean current predictions

**Geographic Coverage:**
- Atlantic Coast: 50+ stations
- Pacific Coast: 40+ stations
- Gulf of Mexico: 30+ stations
- Great Lakes: 20+ stations

**Key Metrics:**
- Wave height (feet/meters)
- Wave period (seconds)
- Water temperature (°C/°F)
- Tide levels (feet relative to MLLW)
- Water salinity (ppt)
- Current speed and direction

---

### 2. 🌤️ Atmospheric Pond

**Purpose:** Weather forecasts, alerts, and observations

**Data Sources:**
- National Weather Service API (api.weather.gov)
- Active weather alerts
- Point forecasts and gridded data

**Geographic Coverage:**
- All 50 US states
- Major cities: 50+
- NWS forecast offices: 122
- Observation stations: 1000+

**Key Metrics:**
- Temperature (°F)
- Wind speed/direction (mph)
- Humidity (%)
- Barometric pressure (inHg)
- Visibility (miles)
- Weather conditions
- Forecast confidence

**Alert Types:**
- Tornado Warning/Watch
- Severe Thunderstorm Warning/Watch
- Flash Flood Warning
- Winter Storm Warning
- Heat Advisory
- Hurricane Warning

---

### 3. 🌡️ Climate Pond

**Purpose:** Historical climate data and normals

**Data Sources:**
- NOAA Climate Data Online (CDO) API
- NCEI datasets
- Climate normals (1991-2020)

**Geographic Coverage:**
- GHCN stations: 10,000+
- US coverage: All states
- Historical range: 1950-present

**Key Metrics:**
- Daily temperature max/min (°F)
- Precipitation (inches)
- Snowfall (inches)
- Snow depth (inches)
- Heating/cooling degree days
- Climate normals

**Datasets:**
- GHCND: Global Historical Climatology Network Daily
- NORMAL_DLY: Daily climate normals
- PRECIP_15: 15-minute precipitation

---

### 4. 🛰️ Spatial Pond

**Purpose:** Radar and satellite imagery metadata

**Data Sources:**
- NEXRAD radar network
- GOES satellite products
- NESDIS data catalogs

**Geographic Coverage:**
- Radar sites: 160+
- Satellite coverage: CONUS + territories
- Update frequency: 5-15 minutes

**Key Metrics:**
- Radar reflectivity (dBZ)
- Product availability
- Coverage maps
- Image timestamps

---

### 5. 🏞️ Terrestrial Pond

**Purpose:** River, stream, and precipitation data

**Data Sources:**
- USGS Water Services API
- NWS precipitation products
- River forecast centers

**Geographic Coverage:**
- USGS gauges: 10,000+
- Major rivers: All US watersheds
- Flash flood monitoring sites

**Key Metrics:**
- Stream flow (cubic feet/second)
- Gauge height (feet)
- Water temperature (°C)
- Flood stage levels
- Precipitation accumulation

---

### 6. ⚓ Buoy Pond

**Purpose:** Offshore marine meteorological data

**Data Sources:**
- NDBC real-time data
- Meteorological buoys
- Wave measurement buoys

**Geographic Coverage:**
- Offshore buoys: 150+
- Coastal buoys: 50+
- International waters: 20+

**Key Metrics:**
- Significant wave height (feet)
- Dominant wave period (seconds)
- Average wave period (seconds)
- Wind speed/direction (knots)
- Air temperature (°F)
- Sea surface temperature (°F)
- Barometric pressure (mb)

---

## 🔗 Endpoint Catalog

### Oceanic Endpoints

#### Buoy Data (Real-time)
```
Base URL: https://www.ndbc.noaa.gov/data/realtime2/
Format: Space-delimited text
Update: 10 minutes
```

**Major Stations:**
- 44013 (Boston, MA)
- 41010 (Canaveral, FL)
- 46022 (Eel River, CA)
- 46246 (San Francisco, CA)
- 51000 (Hawaii)

**Data Fields:**
```
#YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP
```

#### Tide Stations
```
Base URL: https://api.tidesandcurrents.noaa.gov/api/prod/datagetter
Format: JSON
Update: 6 minutes
```

**Products Available:**
- `water_level` - Water level data
- `predictions` - Tidal predictions
- `currents` - Current speed/direction
- `wind` - Wind observations
- `air_temperature` - Air temperature
- `water_temperature` - Water temperature

**Major Stations:**
- 8443970 (Boston, MA)
- 8516945 (Kings Point, NY)
- 8636580 (Yorktown, VA)
- 8720030 (Clearwater Beach, FL)
- 9414290 (San Francisco, CA)

**Example Request:**
```
https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?
  station=8443970&
  product=water_level&
  datum=MLLW&
  time_zone=gmt&
  units=english&
  format=json&
  date=latest
```

---

### Atmospheric Endpoints

#### Active Weather Alerts
```
Base URL: https://api.weather.gov/alerts/active
Format: GeoJSON
Update: Real-time
```

**Nationwide:**
```
GET /alerts/active
```

**By State:**
```
GET /alerts/active?area=CA
GET /alerts/active?area=NY
```

**Response Structure:**
```json
{
  "features": [
    {
      "properties": {
        "event": "Severe Thunderstorm Warning",
        "severity": "Severe",
        "certainty": "Observed",
        "urgency": "Immediate",
        "areaDesc": "San Diego County",
        "headline": "...",
        "description": "...",
        "instruction": "..."
      }
    }
  ]
}
```

#### Point Forecasts
```
Base URL: https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}/forecast
Format: JSON
Update: Hourly
```

**Major Cities:**

| City | Office | Grid X,Y | Endpoint |
|------|--------|----------|----------|
| New York, NY | OKX | 33,37 | `/gridpoints/OKX/33,37/forecast` |
| Los Angeles, CA | LOX | 154,44 | `/gridpoints/LOX/154,44/forecast` |
| Chicago, IL | LOT | 76,73 | `/gridpoints/LOT/76,73/forecast` |
| Houston, TX | HGX | 67,100 | `/gridpoints/HGX/67,100/forecast` |
| Phoenix, AZ | PSR | 157,64 | `/gridpoints/PSR/157,64/forecast` |
| Miami, FL | MFL | 110,50 | `/gridpoints/MFL/110,50/forecast` |
| Seattle, WA | SEW | 124,67 | `/gridpoints/SEW/124,67/forecast` |
| Boston, MA | BOX | 71,90 | `/gridpoints/BOX/71,90/forecast` |

**Response Structure:**
```json
{
  "properties": {
    "periods": [
      {
        "name": "This Afternoon",
        "temperature": 75,
        "temperatureUnit": "F",
        "windSpeed": "10 mph",
        "windDirection": "SW",
        "shortForecast": "Partly Cloudy",
        "detailedForecast": "..."
      }
    ]
  }
}
```

#### Hourly Forecasts
```
GET /gridpoints/{office}/{gridX},{gridY}/forecast/hourly
```

Returns 156 hourly periods (7 days)

#### Observation Stations
```
GET /stations
GET /stations/{stationId}/observations/latest
```

---

### Climate Endpoints

```
Base URL: https://www.ncdc.noaa.gov/cdo-web/api/v2
Authentication: Token required (header: token: YOUR_TOKEN)
Format: JSON
Rate Limit: 1000 requests/day
```

#### Datasets
```
GET /datasets
```

**Available Datasets:**
- GHCND: Global Historical Climatology Network - Daily
- NORMAL_DLY: Daily climate normals
- NORMAL_HLY: Hourly climate normals
- PRECIP_15: 15-minute precipitation

#### Data Categories
```
GET /datacategories
```

#### Data Types
```
GET /datatypes?datasetid=GHCND
```

**Common Types:**
- TMAX: Maximum temperature
- TMIN: Minimum temperature
- PRCP: Precipitation
- SNOW: Snowfall
- SNWD: Snow depth

#### Stations
```
GET /stations?datasetid=GHCND&extent=38,-98,39,-97
```

#### Data Query
```
GET /data?datasetid=GHCND&stationid=GHCND:USW00094728&startdate=2024-01-01&enddate=2024-01-31
```

---

### Spatial Endpoints

#### NEXRAD Radar
```
Base URL: https://radar.weather.gov/
Format: Various (PNG, NetCDF)
```

**Products:**
- Base Reflectivity
- Base Velocity
- Storm Relative Motion
- Composite Reflectivity

#### GOES Satellite
```
Base URL: https://www.star.nesdis.noaa.gov/
```

**Products:**
- Visible imagery
- Infrared
- Water vapor
- True color

---

### Terrestrial Endpoints

#### USGS Water Services
```
Base URL: https://waterservices.usgs.gov/nwis/iv/
Format: JSON
Update: 15 minutes
```

**Parameters:**
- 00060: Discharge (cubic feet per second)
- 00065: Gauge height (feet)
- 00010: Temperature (°C)

**Example:**
```
GET /nwis/iv/?format=json&sites=01646500&parameterCd=00060,00065
```

**Major Gauges:**
- 01646500: Potomac River at Washington, DC
- 02339500: Chattahoochee River at Atlanta, GA
- 06934500: Missouri River at Hermann, MO
- 09380000: Colorado River at Lee's Ferry, AZ

---

## 📊 Schema Reference

### Oceanic Buoys Table

```sql
CREATE EXTERNAL TABLE noaa_gold_dev.oceanic_buoys (
    station_id STRING,
    station_name STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    timestamp TIMESTAMP,
    wave_height DOUBLE,
    wave_period DOUBLE,
    sea_surface_temperature DOUBLE,
    air_temperature DOUBLE,
    wind_speed DOUBLE,
    wind_direction INT,
    barometric_pressure DOUBLE,
    wind_gust DOUBLE,
    dominant_wave_period DOUBLE,
    average_wave_period DOUBLE,
    water_temperature DOUBLE
)
PARTITIONED BY (date STRING)
STORED AS JSON
LOCATION 's3://bucket/gold/oceanic/buoys/';
```

### Oceanic Tides Table

```sql
CREATE EXTERNAL TABLE noaa_gold_dev.oceanic_tides (
    station_id STRING,
    station_name STRING,
    state STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    timestamp TIMESTAMP,
    water_level DOUBLE,
    sigma DOUBLE,
    flags STRING,
    quality STRING
)
PARTITIONED BY (date STRING)
STORED AS JSON
LOCATION 's3://bucket/gold/oceanic/tides/';
```

### Atmospheric Forecasts Table

```sql
CREATE EXTERNAL TABLE noaa_gold_dev.atmospheric_forecasts (
    location_id STRING,
    location_name STRING,
    state STRING,
    region STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    timestamp TIMESTAMP,
    current_period STRUCT<
        name: STRING,
        temperature: INT,
        temperature_unit: STRING,
        wind_speed: STRING,
        wind_direction: STRING,
        short_forecast: STRING
    >,
    forecast_periods_count INT,
    forecast_high_temp INT,
    forecast_low_temp INT
)
PARTITIONED BY (date STRING)
STORED AS JSON
LOCATION 's3://bucket/gold/atmospheric/forecasts/';
```

### Atmospheric Alerts Table

```sql
CREATE EXTERNAL TABLE noaa_gold_dev.atmospheric_alerts (
    timestamp STRING,
    total_alerts INT,
    alert_summary ARRAY<STRUCT<
        event_type: STRING,
        severity: STRING,
        alert_count: INT,
        sample_areas: ARRAY<STRING>
    >>
)
PARTITIONED BY (date STRING)
STORED AS JSON
LOCATION 's3://bucket/gold/atmospheric/alerts/';
```

### Climate Daily Table

```sql
CREATE EXTERNAL TABLE noaa_gold_dev.climate_daily (
    station_id STRING,
    station_name STRING,
    state STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    temperature_max DOUBLE,
    temperature_min DOUBLE,
    precipitation DOUBLE,
    snowfall DOUBLE,
    snow_depth DOUBLE,
    observation_time TIMESTAMP
)
PARTITIONED BY (date STRING)
STORED AS JSON
LOCATION 's3://bucket/gold/climate/daily/';
```

---

## 🔍 Query Patterns

### Basic Queries

#### 1. Current Conditions by Location

```sql
-- Get current weather for a specific state
SELECT 
    location_name,
    current_period.temperature as temp,
    current_period.wind_speed,
    current_period.short_forecast
FROM noaa_gold_dev.atmospheric_forecasts
WHERE state = 'CA'
    AND date = date_format(current_date, '%Y-%m-%d')
ORDER BY location_name;
```

#### 2. Recent Ocean Conditions

```sql
-- High waves in the last 24 hours
SELECT 
    station_name,
    wave_height,
    wind_speed,
    sea_surface_temperature,
    timestamp
FROM noaa_gold_dev.oceanic_buoys
WHERE date >= date_format(current_date - interval '1' day, '%Y-%m-%d')
    AND wave_height > 8.0
ORDER BY wave_height DESC
LIMIT 20;
```

#### 3. Climate Comparison

```sql
-- Temperature extremes by station
SELECT 
    station_id,
    station_name,
    AVG(temperature_max) as avg_high,
    MAX(temperature_max) as record_high,
    AVG(temperature_min) as avg_low,
    MIN(temperature_min) as record_low
FROM noaa_gold_dev.climate_daily
WHERE date >= date_format(current_date - interval '30' day, '%Y-%m-%d')
GROUP BY station_id, station_name
ORDER BY avg_high DESC;
```

### Federated Queries

#### 4. Coastal Weather Analysis

```sql
-- Compare air and water temps along coast
SELECT 
    a.location_name,
    a.state,
    a.current_period.temperature as air_temp,
    AVG(o.water_temperature) as avg_water_temp,
    AVG(b.sea_surface_temperature) as avg_sst,
    a.date
FROM noaa_gold_dev.atmospheric_forecasts a
LEFT JOIN noaa_gold_dev.oceanic_tides o
    ON a.state = o.state
    AND a.date = o.date
LEFT JOIN noaa_gold_dev.oceanic_buoys b
    ON CAST(a.latitude AS DECIMAL(10,2)) = CAST(b.latitude AS DECIMAL(10,2))
    AND a.date = b.date
WHERE a.date >= date_format(current_date - interval '7' day, '%Y-%m-%d')
    AND o.water_temperature IS NOT NULL
GROUP BY a.location_name, a.state, a.current_period.temperature, a.date
ORDER BY a.date DESC, a.state;
```

#### 5. Multi-Source Regional Summary

```sql
-- Complete environmental picture by state
SELECT 
    COALESCE(a.state, c.state, o.state) as state,
    
    -- Atmospheric data
    COUNT(DISTINCT a.location_name) as forecast_locations,
    AVG(a.current_period.temperature) as avg_air_temp,
    
    -- Climate data
    AVG(c.precipitation) as avg_precipitation,
    AVG(c.temperature_max) as avg_daily_high,
    
    -- Oceanic data
    COUNT(DISTINCT o.station_id) as tide_stations,
    AVG(o.water_level) as avg_water_level,
    
    date_format(current_date, '%Y-%m-%d') as report_date
    
FROM noaa_gold_dev.atmospheric_forecasts a
FULL OUTER JOIN noaa_gold_dev.climate_daily c
    ON a.state = c.state
    AND a.date = c.date
FULL OUTER JOIN noaa_gold_dev.oceanic_tides o
    ON a.state = o.state
    AND a.date = o.date
    
WHERE a.date = date_format(current_date, '%Y-%m-%d')
   OR c.date = date_format(current_date, '%Y-%m-%d')
   OR o.date = date_format(current_date, '%Y-%m-%d')
   
GROUP BY COALESCE(a.state, c.state, o.state)
ORDER BY state;
```

#### 6. Extreme Conditions Finder

```sql
-- Find all locations with extreme conditions
WITH extreme_temps AS (
    SELECT 
        location_name as location,
        state,
        current_period.temperature as value,
        'High Temperature' as condition,
        'atmospheric' as source,
        date
    FROM noaa_gold_dev.atmospheric_forecasts
    WHERE current_period.temperature > 95
        AND date >= date_format(current_date - interval '1' day, '%Y-%m-%d')
),
extreme_waves AS (
    SELECT 
        station_name as location,
        'Ocean' as state,
        wave_height as value,
        'High Waves' as condition,
        'oceanic' as source,
        date
    FROM noaa_gold_dev.oceanic_buoys
    WHERE wave_height > 12.0
        AND date >= date_format(current_date - interval '1' day, '%Y-%m-%d')
),
heavy_precip AS (
    SELECT 
        station_name as location,
        state,
        precipitation as value,
        'Heavy Precipitation' as condition,
        'climate' as source,
        date
    FROM noaa_gold_dev.climate_daily
    WHERE precipitation > 2.0
        AND date >= date_format(current_date - interval '1' day, '%Y-%m-%d')
)
SELECT * FROM extreme_temps
UNION ALL
SELECT * FROM extreme_waves
UNION ALL
SELECT * FROM heavy_precip
ORDER BY date DESC, condition, value DESC;
```

### Time Series Queries

#### 7. Weekly Trend Analysis

```sql
-- Trend analysis across all ponds
SELECT 
    date,
    COUNT(DISTINCT af.location_name) as atmos_locations,
    AVG(af.current_period.temperature) as avg_air_temp,
    COUNT(DISTINCT ob.station_id) as ocean_buoys,
    AVG(ob.wave_height) as avg_wave_height,
    COUNT(DISTINCT cd.station_id) as climate_stations,
    AVG(cd.temperature_max) as avg_daily_high
FROM noaa_gold_dev.atmospheric_forecasts af
FULL OUTER JOIN noaa_gold_dev.oceanic_buoys ob
    ON af.date = ob.date
FULL OUTER JOIN noaa_gold_dev.climate_daily cd
    ON af.date = cd.date
WHERE af.date >= date_format(current_date - interval '7' day, '%Y-%m-%d')
GROUP BY date
ORDER BY date DESC;
```

#### 8. Location History

```sql
-- Complete history for a specific location
SELECT 
    'atmospheric' as data_type,
    location_name,
    current_period.temperature as value,
    'temperature_f' as metric,
    date
FROM noaa_gold_dev.atmospheric_forecasts
WHERE location_name = 'New York City'
    AND date >= date_format(current_date - interval '30' day, '%Y-%m-%d')

UNION ALL

SELECT 
    'climate' as data_type,
    station_name as location_name,
    temperature_max as value,
    'temperature_max_f' as metric,
    date
FROM noaa_gold_dev.climate_daily
WHERE station_name LIKE '%NEW YORK%'
    AND date >= date_format(current_date - interval '30' day, '%Y-%m-%d')

ORDER BY date DESC, data_type;
```

---

## 🔗 Cross-Pond Relationships

### Data Element Mapping

| Element | Oceanic | Atmospheric | Climate | Spatial | Terrestrial | Buoy |
|---------|---------|-------------|---------|---------|-------------|------|
| Temperature | Water | Air | Daily | - | Water | Air/Water |
| Location | Lat/Lon | Lat/Lon | Lat/Lon | Coverage | Lat/Lon | Lat/Lon |
| Wind | Speed/Dir | Speed/Dir | - | - | - | Speed/Dir |
| Pressure | Baro | Baro | - | - | - | Baro |
| Precipitation | - | Forecast | Daily | - | Real-time | - |
| Water Level | Tides | - | - | - | Rivers | - |
| Waves | Height/Period | - | - | - | - | Height/Period |

### Join Strategies

#### By State
```sql
ON pond1.state = pond2.state AND pond1.date = pond2.date
```

#### By Coordinates (nearby locations)
```sql
ON CAST(pond1.latitude AS DECIMAL(10,2)) = CAST(pond2.latitude AS DECIMAL(10,2))
   AND CAST(pond1.longitude AS DECIMAL(10,2)) = CAST(pond2.longitude AS DECIMAL(10,2))
```

#### By Date/Time
```sql
ON pond1.date = pond2.date
```

#### By Station ID (when available)
```sql
ON pond1.station_id = pond2.station_id
```

---

## 💡 Use Cases

### 1. Beach Safety Monitoring

**Data Required:** Oceanic (waves, tides) + Atmospheric (weather, wind)

**Query:**
```sql
SELECT 
    o.station_name as beach,
    o.wave_height,
    o.water_temperature,
    a.current_period.temperature as air_temp,
    a.current_period.wind_speed,
    CASE 
        WHEN o.wave_height > 10 THEN 'High Surf Advisory'
        WHEN o.wave_height > 6 THEN 'Caution'
        ELSE 'Normal'
    END as safety_status
FROM noaa_gold_dev.oceanic_buoys o
LEFT JOIN noaa_gold_dev.atmospheric_forecasts a
    ON CAST(o.latitude AS DECIMAL(10,2)) = CAST(a.latitude AS DECIMAL(10,2))
WHERE o.date = date_format(current_date, '%Y-%m-%d')
ORDER BY o.wave_height DESC;
```

### 2. Agricultural Planning

**Data Required:** Climate (precipitation, temperature) + Atmospheric (forecasts)

**Query:**
```sql
SELECT 
    c.state,
    AVG(c.precipitation) as avg_precip_last_30_days,
    AVG(c.temperature_max) as avg_high,
    AVG(a.current_period.temperature) as forecast_temp
FROM noaa_gold_dev.climate_daily c
LEFT JOIN noaa_gold_dev.atmospheric_forecasts a
    ON c.state = a.state
WHERE c.date >= date_format(current_date - interval '30' day, '%Y-%m-%d')
GROUP BY c.state
ORDER BY avg_precip_last_30_days DESC;
```

### 3. Maritime Navigation

**Data Required:** Oceanic (buoys, tides) + Atmospheric (wind, visibility)

**Query:**
```sql
SELECT 
    b.station_name,
    b.wave_height,
    b.wind_speed as buoy_wind,
    b.visibility,
    t.water_level,
    a.current_period.short_forecast
FROM noaa_gold_dev.oceanic_buoys b
LEFT JOIN noaa_gold_dev.oceanic_tides t
    ON b.station_id = t.station_id
LEFT JOIN noaa_gold_dev.atmospheric_forecasts a
    ON CAST(b.latitude AS DECIMAL(10,2)) = CAST(a.latitude AS DECIMAL(10,2))
WHERE b.date = date_format(current_date, '%Y-%m-%d')
ORDER BY b.wave_height DESC;
```

### 4. Flood Monitoring

**Data Required:** Terrestrial (river gauges) + Climate (precipitation) + Atmospheric (forecasts)

**Query:**
```sql
-- Combine river levels with recent precipitation and forecasts
SELECT 
    t.station_id,
    t.gauge_height,
    t.discharge,
    AVG(c.precipitation) as precip_last_7_days,
    a.current_period.short_forecast
FROM noaa_gold_dev.terrestrial_gauges t
LEFT JOIN noaa_gold_dev.climate_daily c
    ON t.state = c.state
    AND c.date >= date_format(current_date - interval '7' day, '%Y-%m-%d')
LEFT JOIN noaa_gold_dev.atmospheric_forecasts a
    ON t.state = a.state
WHERE t.date = date_format(current_date, '%Y-%m-%d')
    AND t.gauge_height > t.flood_stage
GROUP BY t.station_id, t.gauge_height, t.discharge, a.current_period.short_forecast
ORDER BY t.gauge_height DESC;
```

### 5. Emergency Response

**Data Required:** Atmospheric (alerts) + All ponds (conditions)

**Query:**
```sql
-- Get all active alerts with current conditions
SELECT 
    al.total_alerts,
    al.alert_summary,
    af.location_name,
    af.state,
    af.current_period.temperature,
    af.current_period.wind_speed,
    ob.wave_height,
    cd.precipitation
FROM noaa_gold_dev.atmospheric_alerts al
JOIN noaa_gold_dev.atmospheric_forecasts af
    ON al.date = af.date
LEFT JOIN noaa_gold_dev.oceanic_buoys ob
    ON af.date = ob.date
    AND CAST(af.latitude AS DECIMAL(10,2)) = CAST(ob.latitude AS DECIMAL(10,2))
LEFT JOIN noaa_gold_dev.climate_daily cd
    ON af.state = cd.state
    AND af.date = cd.date
WHERE al.total_alerts > 0
    AND al.date = date_format(current_date, '%Y-%m-%d')
ORDER BY al.total_alerts DESC;
```

---

## 📈 Data Freshness SLAs

| Pond | Target Freshness | Actual Freshness | Ingestion Frequency |
|------|-----------------|------------------|---------------------|
| Oceanic | < 15 minutes | ~12 minutes | Every 15 minutes |
| Atmospheric | < 15 minutes | ~10 minutes | Every 15 minutes |
| Climate | < 1 hour | ~45 minutes | Every 1 hour |
| Spatial | < 30 minutes | ~25 minutes | Every 30 minutes |
| Terrestrial | < 30 minutes | ~20 minutes | Every 30 minutes |
| Buoy | < 15 minutes | ~12 minutes | Every 15 minutes |

---

## 🔐 Data Access Patterns

### Read Patterns

1. **Point Queries** - Single location, current conditions
2. **Range Queries** - Time-based analysis (last 7 days)
3. **Aggregation Queries** - State/region summaries
4. **Join Queries** - Cross-pond federated queries

### Optimization Tips

```sql
-- Always use partition pruning
WHERE date >= date_format(current_date - interval '7' day, '%Y-%m-%d')

-- Use CAST for coordinate joins
CAST(latitude AS DECIMAL(10,2))

-- Limit result sets
LIMIT 1000

-- Use aggregation when appropriate
GROUP BY state, date
```

---

## 📝 Notes

- All timestamps are in UTC
- Temperature units: °F (can convert to °C)
- Distance units: feet, miles (can convert to meters, km)
- Pressure units: inches Hg, millibars
- Wind speed: mph, knots
- Partitions by date for efficient querying
- Data retention follows medallion architecture rules

---

**Last Updated:** November 2024  
**Version:** 1.0  
**Maintained By:** NOAA Federated Data Lake Team