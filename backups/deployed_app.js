/**
 * NOAA Data Lake Chatbot - Main Application
 * Version: 1.0
 */

// Configuration
const CONFIG = {
  // UPDATE THESE WITH YOUR ACTUAL API GATEWAY URLS
  API_BASE_URL: "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev",
  PLAINTEXT_ENDPOINT: "/query",
  PASSTHROUGH_ENDPOINT: "/passthrough",

  // For local testing, you can use:
  // API_BASE_URL: 'http://localhost:3000',

  MAX_RETRIES: 2,
  TIMEOUT: 30000,

  // Cache busting
  CACHE_BUSTER: Date.now(),

  // Pond to service mapping
  POND_TO_SERVICE: {
    atmospheric: "nws",
    oceanic: "tides",
    buoy: "ndbc",
    climate: "cdo",
    archive: "ncei",
  },
};

// Quick Actions Pool - 50 diverse queries for major US cities and scenarios
const QUICK_ACTIONS_POOL = [
  {
    icon: "fa-exclamation-triangle",
    label: "NYC Alerts",
    query:
      "Are there any severe weather warnings or advisories for New York City?",
  },
  {
    icon: "fa-water",
    label: "LA Tides",
    query:
      "What are the current tide levels and predictions for Los Angeles harbors?",
  },
  {
    icon: "fa-plane",
    label: "Chicago Weather",
    query: "Current weather conditions at Chicago O'Hare airport",
  },
  {
    icon: "fa-ship",
    label: "Miami Marine",
    query: "What are the marine conditions and wave heights near Miami Beach?",
  },
  {
    icon: "fa-temperature-high",
    label: "Phoenix Heat",
    query: "What's the temperature in Phoenix and heat index forecast?",
  },
  {
    icon: "fa-cloud-rain",
    label: "Seattle Rain",
    query: "Precipitation forecast for Seattle for the next 48 hours",
  },
  {
    icon: "fa-snowflake",
    label: "Denver Snow",
    query: "Any winter weather advisories or snow forecasts for Denver?",
  },
  {
    icon: "fa-hurricane",
    label: "Gulf Hurricanes",
    query:
      "Are there any active tropical systems or hurricanes in the Gulf of Mexico?",
  },
  {
    icon: "fa-water",
    label: "SF Bay Tides",
    query: "High and low tide times for San Francisco Bay tomorrow",
  },
  {
    icon: "fa-wind",
    label: "Boston Wind",
    query: "Wind speed and direction forecast for Boston harbor",
  },
  {
    icon: "fa-sun",
    label: "Las Vegas Sun",
    query: "UV index and temperature forecast for Las Vegas",
  },
  {
    icon: "fa-cloud-bolt",
    label: "Dallas Storms",
    query: "Thunderstorm risk and severe weather outlook for Dallas-Fort Worth",
  },
  {
    icon: "fa-temperature-low",
    label: "Minneapolis Cold",
    query: "Current temperature and wind chill for Minneapolis",
  },
  {
    icon: "fa-smog",
    label: "Houston Air",
    query: "Air quality and weather conditions in Houston",
  },
  {
    icon: "fa-life-ring",
    label: "Atlantic Buoys",
    query: "Latest buoy data from the Atlantic Ocean near North Carolina",
  },
  {
    icon: "fa-chart-line",
    label: "Portland Climate",
    query:
      "Historical temperature trends for Portland, Oregon over the past year",
  },
  {
    icon: "fa-water",
    label: "NOLA Flooding",
    query: "Coastal flooding predictions and tide levels for New Orleans",
  },
  {
    icon: "fa-umbrella",
    label: "Atlanta Rain",
    query: "Rain forecast and accumulation predictions for Atlanta",
  },
  {
    icon: "fa-icicles",
    label: "Anchorage Ice",
    query: "Freezing conditions and ice warnings for Anchorage, Alaska",
  },
  {
    icon: "fa-volcano",
    label: "Hawaii Volcano",
    query: "Weather conditions and air quality near Hawaiian volcanoes",
  },
  {
    icon: "fa-mountain",
    label: "Salt Lake Snow",
    query: "Mountain weather and snow conditions near Salt Lake City",
  },
  {
    icon: "fa-tornado",
    label: "OKC Tornadoes",
    query: "Tornado watch or warning status for Oklahoma City area",
  },
  {
    icon: "fa-waves",
    label: "San Diego Surf",
    query: "Wave height and surf conditions for San Diego beaches",
  },
  {
    icon: "fa-cloud-sun",
    label: "Tampa Weather",
    query: "Current weather and forecast for Tampa Bay area",
  },
  {
    icon: "fa-thermometer-half",
    label: "Austin Temp",
    query: "Temperature trends and forecast for Austin, Texas",
  },
  {
    icon: "fa-flag",
    label: "DC Weather",
    query: "Weather conditions in Washington DC and any alerts",
  },
  {
    icon: "fa-bridge",
    label: "Oakland Bay",
    query: "Marine forecast for San Francisco Bay near Oakland",
  },
  {
    icon: "fa-landmark",
    label: "Philly Weather",
    query: "Current conditions and precipitation forecast for Philadelphia",
  },
  {
    icon: "fa-music",
    label: "Nashville Storms",
    query: "Severe weather outlook for Nashville, Tennessee",
  },
  {
    icon: "fa-anchor",
    label: "Virginia Beach",
    query: "Ocean conditions and rip current risk at Virginia Beach",
  },
  {
    icon: "fa-cloud-showers-heavy",
    label: "Portland Floods",
    query: "Flood warnings and river levels near Portland, Maine",
  },
  {
    icon: "fa-sun-cloud",
    label: "San Antonio",
    query: "Weather forecast for San Antonio for the next 3 days",
  },
  {
    icon: "fa-water-ladder",
    label: "Lake Michigan",
    query:
      "Water temperature and wave conditions on Lake Michigan near Chicago",
  },
  {
    icon: "fa-wind",
    label: "Windy City",
    query: "Wind advisory status and gusts for Chicago area",
  },
  {
    icon: "fa-cloud-fog",
    label: "San Jose Fog",
    query: "Visibility and fog conditions in San Jose, California",
  },
  {
    icon: "fa-bolt",
    label: "Lightning Risk",
    query: "Lightning strike probability for outdoor activities in Tampa",
  },
  {
    icon: "fa-sailboat",
    label: "Charleston SC",
    query: "Sailing conditions and marine weather for Charleston harbor",
  },
  {
    icon: "fa-cloud-moon",
    label: "Night Weather",
    query: "Overnight low temperatures and conditions for Indianapolis",
  },
  {
    icon: "fa-umbrella-beach",
    label: "Myrtle Beach",
    query: "Beach weather and UV index for Myrtle Beach, South Carolina",
  },
  {
    icon: "fa-road",
    label: "Travel Weather",
    query: "Interstate weather conditions between New York and Boston",
  },
  {
    icon: "fa-fire",
    label: "Wildfire Risk",
    query: "Fire weather warnings and dry conditions for California",
  },
  {
    icon: "fa-otter",
    label: "Monterey Bay",
    query: "Ocean temperature and marine life conditions in Monterey Bay",
  },
  {
    icon: "fa-tint",
    label: "Drought Data",
    query: "Precipitation deficit and drought status for Southwest US",
  },
  {
    icon: "fa-cloud-rain",
    label: "Flood Risk",
    query: "Flash flood warnings and rainfall totals for Louisiana",
  },
  {
    icon: "fa-skiing",
    label: "Mountain Weather",
    query: "Snow conditions and avalanche risk for Colorado mountains",
  },
  {
    icon: "fa-fish",
    label: "Fishing Weather",
    query:
      "Best fishing conditions based on barometric pressure in Chesapeake Bay",
  },
  {
    icon: "fa-kiwi-bird",
    label: "Migration Weather",
    query: "Weather impact on bird migration along Atlantic flyway",
  },
  {
    icon: "fa-tractor",
    label: "Farm Weather",
    query: "Agricultural weather forecast and soil conditions for Iowa",
  },
  {
    icon: "fa-gem",
    label: "Air Quality",
    query: "Air quality index and pollution levels for major West Coast cities",
  },
  {
    icon: "fa-compass",
    label: "Navigation",
    query: "Marine navigation conditions and visibility for Puget Sound",
  },
];

// Fallback pond metadata when API is unavailable
const FALLBACK_PONDS = {
  atmospheric: {
    name: "Atmospheric",
    description: "Weather forecasts, alerts, and observations from NWS",
    icon: "fa-cloud-sun",
    endpoints: [
      { name: "Active Alerts", service: "NWS", url: "/alerts/active" },
      { name: "Point Forecasts", service: "NWS", url: "/gridpoints" },
      {
        name: "Hourly Forecasts",
        service: "NWS",
        url: "/gridpoints/*/forecast/hourly",
      },
      { name: "Observations", service: "NWS", url: "/stations/*/observations" },
      { name: "Radar Stations", service: "NWS", url: "/radar/stations" },
      { name: "Zone Forecasts", service: "NWS", url: "/zones" },
      { name: "Products", service: "NWS", url: "/products" },
      { name: "Glossary", service: "NWS", url: "/glossary" },
    ],
  },
  oceanic: {
    name: "Oceanic",
    description: "Tides, currents, and water levels from CO-OPS",
    icon: "fa-water",
    endpoints: [
      {
        name: "Water Level",
        service: "COOPS",
        url: "/datagetter?product=water_level",
      },
      {
        name: "Predictions",
        service: "COOPS",
        url: "/datagetter?product=predictions",
      },
      {
        name: "Currents",
        service: "COOPS",
        url: "/datagetter?product=currents",
      },
      {
        name: "Air Temperature",
        service: "COOPS",
        url: "/datagetter?product=air_temperature",
      },
      {
        name: "Water Temperature",
        service: "COOPS",
        url: "/datagetter?product=water_temperature",
      },
      { name: "Wind", service: "COOPS", url: "/datagetter?product=wind" },
      {
        name: "Air Pressure",
        service: "COOPS",
        url: "/datagetter?product=air_pressure",
      },
      {
        name: "Datums",
        service: "COOPS",
        url: "/mdapi/prod/webapi/stations/*/datums.json",
      },
    ],
  },
  buoy: {
    name: "Buoy",
    description: "Real-time marine buoy data from NDBC",
    icon: "fa-ship",
    endpoints: [
      {
        name: "Standard Met Data",
        service: "NDBC",
        url: "/data/realtime2/*.txt",
      },
      {
        name: "Spectral Wave Data",
        service: "NDBC",
        url: "/data/realtime2/*.spec",
      },
      { name: "Ocean Data", service: "NDBC", url: "/data/realtime2/*.ocean" },
      { name: "Active Stations", service: "NDBC", url: "/activestations.xml" },
      { name: "Station Metadata", service: "NDBC", url: "/station_page.php" },
    ],
  },
  climate: {
    name: "Climate",
    description: "Historical climate data from CDO",
    icon: "fa-temperature-high",
    endpoints: [
      { name: "Datasets", service: "CDO", url: "/datasets" },
      { name: "Data Categories", service: "CDO", url: "/datacategories" },
      { name: "Data Types", service: "CDO", url: "/datatypes" },
      {
        name: "Location Categories",
        service: "CDO",
        url: "/locationcategories",
      },
      { name: "Locations", service: "CDO", url: "/locations" },
      { name: "Stations", service: "CDO", url: "/stations" },
      { name: "Data", service: "CDO", url: "/data" },
    ],
  },
  spatial: {
    name: "Spatial",
    description: "Radar and satellite imagery metadata",
    icon: "fa-satellite",
    endpoints: [
      { name: "Radar Products", service: "NEXRAD", url: "/ridge/RadarImg" },
      { name: "Satellite Imagery", service: "GOES", url: "/satellite" },
    ],
  },
  terrestrial: {
    name: "Terrestrial",
    description: "River gauges and stream data from USGS",
    icon: "fa-mountain",
    endpoints: [
      { name: "Instantaneous Values", service: "USGS", url: "/nwis/iv" },
      { name: "Daily Values", service: "USGS", url: "/nwis/dv" },
      { name: "Site Info", service: "USGS", url: "/nwis/site" },
    ],
  },
};

// Application State
const state = {
  currentPond: "all",
  selectedPonds: [],
  messages: [],
  queryCount: 0,
  dataCount: 0,
  pondsQueried: new Set(),
  isProcessing: false,
  availablePonds: null,
};

// DOM Elements
let elements = {};

// Initialize application
document.addEventListener("DOMContentLoaded", () => {
  initializeElements();
  populateQuickActions();
  setupEventListeners();
  loadSessionData();
  checkAPIConnection();
  loadAvailablePonds();
});

function initializeElements() {
  elements = {
    chatMessages: document.getElementById("chatMessages"),
    chatInput: document.getElementById("chatInput"),
    sendBtn: document.getElementById("sendBtn"),
    themeToggle: document.getElementById("themeToggle"),
    queryCount: document.getElementById("queryCount"),
    dataCount: document.getElementById("dataCount"),
    pondOptions: document.querySelectorAll(".pond-option"),
    quickActionBtns: document.querySelectorAll(".quick-action-btn"),
    exampleCards: document.querySelectorAll(".example-card"),
    homeBtn: document.getElementById("homeBtn"),
  };

  // Verify critical elements exist
  const critical = ["chatMessages", "chatInput", "sendBtn"];
  critical.forEach((key) => {
    if (!elements[key]) {
      console.error(`Critical element not found: ${key}`);
    }
  });

  console.log("✓ Elements initialized:", {
    chatMessages: !!elements.chatMessages,
    chatInput: !!elements.chatInput,
    sendBtn: !!elements.sendBtn,
    pondOptions: elements.pondOptions.length,
    quickActionBtns: elements.quickActionBtns.length,
  });
}

function populateQuickActions() {
  const container = document.getElementById("quickActionsContainer");
  if (!container) {
    console.warn("Quick actions container not found");
    return;
  }

  // Shuffle and select 10 random actions from the pool
  const shuffled = [...QUICK_ACTIONS_POOL].sort(() => Math.random() - 0.5);
  const selected = shuffled.slice(0, 10);

  // Clear existing content
  container.innerHTML = "";

  // Create buttons for selected actions
  selected.forEach((action) => {
    const button = document.createElement("button");
    button.className = "quick-action-btn";
    button.setAttribute("data-query", action.query);
    button.innerHTML = `<i class="fas ${action.icon}"></i> ${action.label}`;

    button.addEventListener("click", () => {
      if (elements.chatInput) {
        elements.chatInput.value = action.query;
        handleSendMessage();
      }
    });

    container.appendChild(button);
  });

  // Update elements reference
  elements.quickActionBtns = document.querySelectorAll(".quick-action-btn");
  console.log(
    `✓ Populated ${selected.length} quick actions from pool of ${QUICK_ACTIONS_POOL.length}`,
  );
}

function resetToHome() {
  // Clear chat messages and recreate welcome screen
  if (elements.chatMessages) {
    // Clear all content
    elements.chatMessages.innerHTML = "";

    // Recreate welcome screen with example cards
    const welcomeScreen = document.createElement("div");
    welcomeScreen.className = "welcome-screen";
    welcomeScreen.innerHTML = `
      <i class="fas fa-robot"></i>
      <h2>Welcome to NOAA Data Lake</h2>
      <p>I'm your AI assistant for exploring weather, ocean, climate, and marine data.</p>
      <p>Ask me anything or try one of these examples:</p>
      <div class="welcome-examples">
        <div class="example-card" data-query="What are the current weather conditions in Miami, are there any active hurricane warnings in the Gulf of Mexico, and what's the wave height forecast for the next 24 hours?">
          <i class="fas fa-hurricane"></i>
          <h4>Hurricane & Ocean Safety</h4>
          <p>Weather, warnings & wave forecasts</p>
        </div>
        <div class="example-card" data-query="Show me tide predictions for San Francisco Bay tomorrow at 6 AM and 6 PM, current water temperature, and any marine weather advisories for sailing conditions">
          <i class="fas fa-ship"></i>
          <h4>Marine Planning</h4>
          <p>Tides, temperature & advisories</p>
        </div>
        <div class="example-card" data-query="Compare the historical temperature trends for New York City over the past 5 years with current conditions, and show me any correlation with extreme weather events">
          <i class="fas fa-temperature-high"></i>
          <h4>Climate Analysis</h4>
          <p>Historical trends & correlations</p>
        </div>
        <div class="example-card" data-query="Is there a coastal flooding risk in Charleston, South Carolina considering storm surge predictions, high tide times, current rainfall totals, and historical flooding patterns in the area?">
          <i class="fas fa-house-flood-water"></i>
          <h4>Coastal Flood Assessment</h4>
          <p>Storm surge, tides, rain & history</p>
        </div>
        <div class="example-card" data-query="What are the best fishing conditions off the coast of North Carolina right now based on water temperature, wave heights from nearby buoys, barometric pressure trends, and weather forecast for the next 12 hours?">
          <i class="fas fa-fish"></i>
          <h4>Fishing Conditions</h4>
          <p>Water temp, waves, pressure & weather</p>
        </div>
        <div class="example-card" data-query="Show me all active severe weather warnings across Texas, current radar data, how this compares to historical severe weather patterns, and which counties are most affected">
          <i class="fas fa-bolt"></i>
          <h4>Severe Weather Tracking</h4>
          <p>Warnings, radar, history & zones</p>
        </div>
        <div class="example-card" data-query="Plan a safe maritime route from Boston to Portland Maine considering wind speed and direction, wave heights, visibility forecasts, ocean currents, and any marine weather advisories along the route">
          <i class="fas fa-route"></i>
          <h4>Maritime Navigation</h4>
          <p>Wind, waves, visibility & currents</p>
        </div>
        <div class="example-card" data-query="Analyze climate change indicators for the Pacific Northwest including sea level rise trends, temperature anomalies over the past decade, frequency of extreme precipitation events, and changes in seasonal weather patterns">
          <i class="fas fa-chart-area"></i>
          <h4>Climate Change Impact</h4>
          <p>Sea level, temps, extremes & patterns</p>
        </div>
      </div>
    `;

    elements.chatMessages.appendChild(welcomeScreen);

    // Re-attach click handlers to example cards
    welcomeScreen.querySelectorAll(".example-card").forEach((card) => {
      card.addEventListener("click", () => {
        const query = card.dataset.query;
        if (query && elements.chatInput) {
          elements.chatInput.value = query;
          handleSendMessage();
        }
      });
    });

    // Clear input
    if (elements.chatInput) {
      elements.chatInput.value = "";
    }

    // Scroll to top
    elements.chatMessages.scrollTop = 0;

    console.log("✓ Reset to home screen with examples");
  }
}

function setupEventListeners() {
  // Home button
  if (elements.homeBtn) {
    // Set initial color to white
    elements.homeBtn.style.color = "#ffffff";

    elements.homeBtn.addEventListener("click", resetToHome);
    elements.homeBtn.addEventListener("mouseenter", (e) => {
      e.target.style.color = "var(--primary-color)";
    });
    elements.homeBtn.addEventListener("mouseleave", (e) => {
      e.target.style.color = "#ffffff";
    });
  }

  // Send button
  if (elements.sendBtn) {
    elements.sendBtn.addEventListener("click", handleSendMessage);
  } else {
    console.error("Send button not found - cannot attach click listener");
  }

  // Enter key in textarea
  if (elements.chatInput) {
    elements.chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    });
  }

  // Theme toggle
  if (elements.themeToggle) {
    elements.themeToggle.addEventListener("click", toggleTheme);
  }

  // Pond selector
  elements.pondOptions.forEach((option) => {
    option.addEventListener("click", () => {
      const pond = option.dataset.pond;
      selectPond(pond);
    });
  });

  // Example cards
  elements.exampleCards.forEach((card) => {
    card.addEventListener("click", () => {
      const query = card.dataset.query;
      if (query && elements.chatInput) {
        elements.chatInput.value = query;
        handleSendMessage();
      }
    });
  });

  // Collapsible sections
  document.querySelectorAll(".collapsible-header").forEach((header) => {
    header.addEventListener("click", function () {
      this.classList.toggle("collapsed");
      const section = this.nextElementSibling;
      if (section && section.classList.contains("collapsible-section")) {
        section.classList.toggle("collapsed");

        // Set max-height dynamically to enable smooth transitions
        if (section.classList.contains("collapsed")) {
          section.style.maxHeight = "0";
        } else {
          // Set to scrollHeight for smooth expansion, or use large value
          section.style.maxHeight = section.scrollHeight + "px";
          // Allow content to grow beyond initial calculation
          setTimeout(() => {
            if (!section.classList.contains("collapsed")) {
              section.style.maxHeight = "2000px";
            }
          }, 300);
        }
      }
    });
  });
}

function loadSessionData() {
  // Load any saved session data from localStorage
  try {
    const savedState = localStorage.getItem("noaa_chat_state");
    if (savedState) {
      const parsed = JSON.parse(savedState);
      if (parsed.queryCount) state.queryCount = parsed.queryCount;
      if (parsed.dataCount) state.dataCount = parsed.dataCount;
      updateStats();
    }
  } catch (error) {
    console.warn("Could not load session data:", error);
  }
}

function checkAPIConnection() {
  console.log("Checking API connection...");
  console.log("API Base URL:", CONFIG.API_BASE_URL);

  if (CONFIG.API_BASE_URL.includes("your-api-gateway")) {
    console.warn(
      "⚠️ API_BASE_URL not configured! Update CONFIG.API_BASE_URL in app.js",
    );
  }

  // Sidebar resize variables
  let isResizing = false;
  let startX = 0;
  let startWidth = 0;
  const sidebar = document.getElementById("sidebar");
  const resizer = document.getElementById("resizer");

  if (resizer && sidebar) {
    resizer.addEventListener("mousedown", (e) => {
      isResizing = true;
      startX = e.clientX;
      startWidth = sidebar.offsetWidth;
      document.body.style.cursor = "ew-resize";
      document.body.style.userSelect = "none";
      e.preventDefault();
    });
  }

  document.addEventListener("mousemove", (e) => {
    if (!isResizing) return;

    const delta = e.clientX - startX;
    const newWidth = startWidth + delta;

    // Constrain width between min and max
    if (newWidth >= 180 && newWidth <= 600) {
      sidebar.style.width = newWidth + "px";

      // Toggle wide class based on width
      if (newWidth > 300) {
        sidebar.classList.add("wide");
      } else {
        sidebar.classList.remove("wide");
      }
    }
  });

  document.addEventListener("mouseup", () => {
    if (isResizing) {
      isResizing = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
  });

  console.log("✓ Sidebar resize enabled");
}

async function handleSendMessage() {
  const message = elements.chatInput.value.trim();

  if (!message || state.isProcessing) return;

  // Clear input and reset height
  elements.chatInput.value = "";
  elements.chatInput.style.height = "auto";

  // Add user message
  addMessage("user", message);

  // Show loading
  state.isProcessing = true;
  elements.sendBtn.disabled = true;
  const loadingId = showLoading();

  try {
    let response;

    console.log(
      `Sending query: "${message}" to ${state.currentPond === "all" ? "federated API" : state.currentPond + " pond"}`,
    );

    if (state.currentPond === "all") {
      // Use federated API (plaintext query)
      response = await queryFederatedAPI(message);
    } else {
      // Use direct passthrough to specific pond
      response = await querySpecificPond(state.currentPond, message);
    }

    removeLoading(loadingId);
    displayResponse(response);

    // Update stats
    state.queryCount++;
    updateSessionStats();

    console.log("✓ Query completed successfully");
  } catch (error) {
    removeLoading(loadingId);
    displayError(error);
    console.error("✗ Query failed:", error);
  } finally {
    state.isProcessing = false;
    elements.sendBtn.disabled = false;
    elements.chatInput.focus();
  }
}

async function queryFederatedAPI(query) {
  const url = `${CONFIG.API_BASE_URL}${CONFIG.PLAINTEXT_ENDPOINT}`;

  console.log(`Querying federated API: ${url}`);

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      query: query,
      include_raw_data: true,
      max_results_per_pond: 100,
    }),
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }

  let data = await response.json();

  // Unwrap nested data structure if present, but preserve top-level answer
  if (data.data && !data.answer) {
    data = data.data;
  }

  return {
    type: "federated",
    data: data,
    query: query,
  };
}

async function querySpecificPond(pond, query) {
  const service = CONFIG.POND_TO_SERVICE[pond];

  if (!service) {
    throw new Error(`Unknown pond: ${pond}`);
  }

  // Construct appropriate passthrough query based on pond and message
  const params = buildPassthroughParams(pond, service, query);

  const url = `${CONFIG.API_BASE_URL}${CONFIG.PASSTHROUGH_ENDPOINT}?${params}`;

  console.log(`Querying passthrough API: ${url}`);

  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();

  return {
    type: "passthrough",
    pond: pond,
    service: service,
    data: data,
    query: query,
    apiUrl: url,
  };
}

function buildPassthroughParams(pond, service, query) {
  const params = new URLSearchParams();
  params.append("service", service);

  // Extract location/area from query if possible
  const lowerQuery = query.toLowerCase();

  // Try to extract state abbreviation
  const stateMatch = query.match(/\b([A-Z]{2})\b/);

  // Default parameters based on service
  switch (service) {
    case "nws":
      params.append("endpoint", "alerts/active");
      if (stateMatch) {
        params.append("area", stateMatch[1]);
      }
      // Check for specific endpoint requests
      if (lowerQuery.includes("forecast") || lowerQuery.includes("weather")) {
        if (lowerQuery.includes("hourly")) {
          // Would need coordinates - default to SF
          params.set("endpoint", "gridpoints/MTR/88,126/forecast/hourly");
        } else if (
          lowerQuery.includes("station") ||
          lowerQuery.includes("observation")
        ) {
          params.set("endpoint", "stations/KSFO/observations/latest");
        }
      }
      break;

    case "tides":
      params.append("station", "9414290"); // Default: San Francisco
      params.append("product", "water_level");
      params.append("hours_back", "24");

      if (lowerQuery.includes("prediction")) {
        params.set("product", "predictions");
      } else if (lowerQuery.includes("current")) {
        params.set("product", "currents");
      } else if (lowerQuery.includes("wind")) {
        params.set("product", "wind");
      } else if (lowerQuery.includes("temperature")) {
        params.set("product", "water_temperature");
      }
      break;

    case "ndbc":
      params.append("buoy", "44013"); // Default: Boston

      // Check for specific buoy mentions
      const buoyMatch = query.match(/buoy\s*(\d{5})/i);
      if (buoyMatch) {
        params.set("buoy", buoyMatch[1]);
      }
      break;

    case "cdo":
      params.append("dataset", "GHCND");
      params.append("location", "FIPS:06"); // Default: California
      params.append("days_back", "30");
      break;

    case "ncei":
      params.append("dataset", "global-summary-of-the-day");
      params.append("stations", "USW00014739"); // Default station
      break;
  }

  return params.toString();
}

function displayResponse(response) {
  if (response.type === "federated") {
    displayFederatedResponse(response);
  } else if (response.type === "passthrough") {
    displayPassthroughResponse(response);
  }
}

function displayFederatedResponse(response) {
  const { data, query } = response;

  let messageHTML = "<div>";

  // Handle both nested (data.synthesis) and flat (data.answer) structures
  const synthesis = data.synthesis || data;
  const answer = synthesis.answer;
  const insights = synthesis.insights || [];
  const recordCount =
    data.total_records ||
    synthesis.total_records ||
    synthesis.record_count ||
    0;
  const dataSources = synthesis.data_sources || [];

  // Check if no data was found
  const hasData = recordCount > 0;

  // Display answer
  if (answer) {
    // Configure marked for better rendering
    if (typeof marked !== "undefined") {
      marked.setOptions({
        breaks: true,
        gfm: true,
      });
      messageHTML += `<div class="markdown-content">${marked.parse(answer)}</div>`;
    } else {
      // Fallback to preserving line breaks
      messageHTML += `<div class="markdown-content" style="white-space: pre-wrap;">${escapeHtml(answer)}</div>`;
    }

    // Add helpful message if no data
    if (!hasData) {
      messageHTML += `<div style="margin-top: 15px; padding: 12px; background: rgba(255, 193, 7, 0.1); border-left: 3px solid #ffc107; border-radius: 4px;">
        <strong><i class="fas fa-info-circle"></i> Note:</strong> The data lake appears to be empty or doesn't have data for this query yet.
        <br><br>
        <strong>To populate the data lake:</strong>
        <ul style="margin: 10px 0 0 20px; font-size: 14px;">
          <li>Run the medallion pipeline to ingest NOAA data</li>
          <li>Verify Glue crawlers have processed the data</li>
          <li>Check that Athena tables exist and contain records</li>
        </ul>
      </div>`;
    }
  } else {
    messageHTML += `<p>I processed your query but couldn't generate a response. This may indicate a data structure issue.</p>`;
    messageHTML += `<div style="margin-top: 10px; padding: 10px; background: rgba(255, 152, 0, 0.1); border-left: 3px solid #ff9800; border-radius: 4px;">
      <strong>Debug Info:</strong> Response structure may not match expected format. Check console for details.
    </div>`;
    console.log("Response data structure:", data);
  }

  // Display insights if available
  if (insights && insights.length > 0) {
    messageHTML +=
      '<div style="margin-top: 10px;"><strong>Key Insights:</strong><ul style="margin: 5px 0; padding-left: 20px;">';
    insights.forEach((insight) => {
      messageHTML += `<li>${escapeHtml(insight)}</li>`;
    });
    messageHTML += "</ul></div>";
  }

  // Display pond data if available
  if (data.ponds_queried && data.ponds_queried.length > 0) {
    messageHTML += '<div class="data-summary">';
    data.ponds_queried.forEach((pond) => {
      const summary = pond.summary || {};
      let displayValue = "";
      let displayLabel = pond.pond;

      // Show meaningful data based on pond type
      if (pond.pond.includes("Atmospheric")) {
        if (summary.wind_speed) {
          displayValue = `${summary.wind_speed.min}-${summary.wind_speed.max} knots`;
          displayLabel = "Wind Speed";
        } else if (summary.temperature) {
          displayValue = `${summary.temperature.min}-${summary.temperature.max}°C`;
          displayLabel = "Temperature";
        } else if (summary.stations) {
          displayValue = `${summary.stations} stations`;
          displayLabel = "Weather Stations";
        }
      } else if (pond.pond.includes("Oceanic")) {
        if (summary.stations) {
          displayValue = `${summary.stations} tide stations`;
          displayLabel = "Oceanic Data";
        } else if (summary.measurements) {
          displayValue = `${summary.measurements} measurements`;
          displayLabel = "Ocean Conditions";
        }
      } else if (pond.pond.includes("Buoy")) {
        if (summary.buoys) {
          displayValue = `${summary.buoys} offshore buoys`;
          displayLabel = "Buoy Network";
        } else if (summary.observations) {
          displayValue = `${summary.observations} observations`;
          displayLabel = "Wave Data";
        }
      } else if (pond.pond.includes("Alert")) {
        if (summary.active_alerts) {
          displayValue = `${summary.active_alerts} active`;
          displayLabel = "Weather Alerts";
        }
      } else if (pond.pond.includes("Station")) {
        if (summary.total_stations) {
          displayValue = `${summary.total_stations} locations`;
          displayLabel = "Observation Points";
        }
      }

      // Fallback to record count if no summary
      if (!displayValue) {
        displayValue = `${pond.records_found || pond.record_count || 0}`;
        displayLabel = pond.pond;
      }

      messageHTML += `
                <div class="data-stat">
                    <div class="data-stat-label">${displayLabel}</div>
                    <div class="data-stat-value">${displayValue}</div>
                </div>
            `;

      // Track unique ponds queried
      if (pond.pond) {
        state.pondsQueried.add(pond.pond);
        state.dataCount = state.pondsQueried.size;
      }
    });
    messageHTML += "</div>";

    // Show which ponds were queried - highlight if federated (multi-pond)
    const isFederated = data.federated || data.ponds_queried.length > 1;
    if (isFederated) {
      messageHTML +=
        '<div style="margin-top: 10px; padding: 8px; background: rgba(76, 175, 80, 0.1); border-left: 3px solid #4caf50; border-radius: 4px;">';
      messageHTML +=
        '<strong><i class="fas fa-network-wired"></i> Federated Query:</strong> Data from multiple sources<br>';
    } else {
      messageHTML += '<div style="margin-top: 10px;">';
    }

    data.ponds_queried.forEach((pond) => {
      const summary = pond.summary || {};
      const confidence = pond.relevance_score || pond.confidence || 0;

      // Build meaningful badge text
      let badgeInfo = [];
      if (pond.pond.includes("Atmospheric") && summary.wind_speed) {
        badgeInfo.push(`Wind: ${summary.wind_speed.avg} kt avg`);
        if (summary.temperature) {
          badgeInfo.push(`Temp: ${summary.temperature.avg}°C`);
        }
      } else if (pond.pond.includes("Buoy") && summary.buoys) {
        badgeInfo.push(`${summary.buoys} buoys`);
      } else if (pond.pond.includes("Alert") && summary.active_alerts) {
        badgeInfo.push(`${summary.active_alerts} alerts`);
      } else if (summary.stations) {
        badgeInfo.push(`${summary.stations} stations`);
      }

      // Fallback to relevance if no summary data
      const infoText =
        badgeInfo.length > 0
          ? badgeInfo.join(", ")
          : `${Math.round(confidence * 100)}% relevant`;

      messageHTML += `<span class="pond-badge"><i class="fas fa-database"></i> ${pond.pond} (${infoText})</span> `;
    });
    messageHTML += "</div>";
  } else if (dataSources && dataSources.length > 0) {
    // Fallback: display data_sources if ponds_queried not available
    messageHTML += '<div style="margin-top: 10px;">';
    messageHTML += "<strong>Data Sources:</strong> ";
    dataSources.forEach((source) => {
      messageHTML += `<span class="pond-badge"><i class="fas fa-database"></i> ${source}</span> `;
    });
    messageHTML += "</div>";
  }

  // Display execution time
  if (data.execution_time_ms) {
    messageHTML += `<div style="margin-top: 10px; font-size: 11px; color: var(--text-secondary);">
            <i class="fas fa-clock"></i> Completed in ${data.execution_time_ms}ms
        </div>`;
  }

  // Action buttons
  messageHTML += `
        <div class="action-buttons">
            <button class="action-btn" onclick="viewRawData(${state.messages.length})">
                <i class="fas fa-code"></i> View Raw Data
            </button>
            <button class="action-btn" onclick="exportData(${state.messages.length})">
                <i class="fas fa-download"></i> Export
            </button>
        </div>
    `;

  messageHTML += "</div>";

  const messageData = {
    response: data,
    timestamp: new Date().toISOString(),
  };

  addMessage("bot", messageHTML, messageData);
}

function displayPassthroughResponse(response) {
  const { data, pond, service, query, apiUrl } = response;

  let messageHTML = "<div>";

  messageHTML += `<p>Retrieved data from <strong>${pond}</strong> pond using ${service.toUpperCase()} API.</p>`;

  // Display summary if available
  if (data.summary) {
    const summary = data.summary;
    messageHTML += '<div class="data-summary">';

    // Record count
    if (summary.record_count !== undefined) {
      messageHTML += `
                <div class="data-stat">
                    <div class="data-stat-label">Records</div>
                    <div class="data-stat-value">${summary.record_count}</div>
                </div>
            `;
      // Track pond query (passthrough)
      if (pond) {
        state.pondsQueried.add(pond);
        state.dataCount = state.pondsQueried.size;
      }
    }

    // Total records
    if (summary.total_records !== undefined) {
      messageHTML += `
                <div class="data-stat">
                    <div class="data-stat-label">Total Records</div>
                    <div class="data-stat-value">${summary.total_records}</div>
                </div>
            `;
      // Already tracked above
    }

    // Station info
    if (summary.station_name) {
      messageHTML += `
                <div class="data-stat">
                    <div class="data-stat-label">Station</div>
                    <div class="data-stat-value" style="font-size: 14px;">${summary.station_name}</div>
                </div>
            `;
    }

    // Buoy info
    if (summary.buoy_id) {
      messageHTML += `
                <div class="data-stat">
                    <div class="data-stat-label">Buoy ID</div>
                    <div class="data-stat-value">${summary.buoy_id}</div>
                </div>
            `;
    }

    messageHTML += "</div>";

    // Statistics for tides
    if (summary.statistics) {
      const stats = summary.statistics;
      messageHTML +=
        '<div style="margin-top: 10px;"><strong>Statistics:</strong><br>';
      messageHTML += `Min: ${stats.min?.toFixed(2)} | Max: ${stats.max?.toFixed(2)} | Avg: ${stats.avg?.toFixed(2)}`;
      messageHTML += "</div>";
    }

    // Sample alerts
    if (summary.sample_alerts && summary.sample_alerts.length > 0) {
      messageHTML +=
        '<div style="margin-top: 10px;"><strong>Sample Alerts:</strong><ul style="margin: 5px 0; padding-left: 20px;">';
      summary.sample_alerts.slice(0, 3).forEach((alert) => {
        messageHTML += `<li><strong>${alert.event}</strong> - ${alert.severity} - ${alert.area}</li>`;
      });
      messageHTML += "</ul></div>";
    }
  }

  // Show data pond
  messageHTML += `<div style="margin-top: 10px;">
        <span class="pond-badge"><i class="fas fa-database"></i> ${data.data_pond || pond}</span>
    </div>`;

  // Show API URL
  messageHTML += `<div class="api-url-display">
        <i class="fas fa-link"></i> ${apiUrl.replace(CONFIG.API_BASE_URL, "")}
    </div>`;

  // Action buttons
  messageHTML += `
        <div class="action-buttons">
            <button class="action-btn" onclick="viewRawData(${state.messages.length})">
                <i class="fas fa-code"></i> View Raw Data
            </button>
            <button class="action-btn" onclick="exportData(${state.messages.length})">
                <i class="fas fa-download"></i> Export
            </button>
        </div>
    `;

  messageHTML += "</div>";

  const messageData = {
    response: data,
    timestamp: new Date().toISOString(),
  };

  addMessage("bot", messageHTML, messageData);
}

function displayError(error) {
  console.error("Error:", error);

  const errorHTML = `
        <div>
            <p>I encountered an error while processing your request.</p>
            <div class="error-message">
                <i class="fas fa-exclamation-triangle"></i> ${escapeHtml(error.message)}
            </div>
            <p style="margin-top: 10px; font-size: 13px;">
                Please check:
                <ul style="margin: 5px 0; padding-left: 20px; font-size: 13px;">
                    <li>Your API Gateway URL is configured correctly</li>
                    <li>The API endpoints are deployed</li>
                    <li>Your network connection is stable</li>
                </ul>
            </p>
        </div>
    `;

  addMessage("bot", errorHTML);
}

function addMessage(type, content, data = null) {
  // Remove welcome screen if present
  const welcomeScreen = elements.chatMessages.querySelector(".welcome-screen");
  if (welcomeScreen) {
    welcomeScreen.remove();
  }

  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${type}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.innerHTML =
    type === "user"
      ? '<i class="fas fa-user"></i>'
      : '<i class="fas fa-robot"></i>';

  const messageContent = document.createElement("div");
  messageContent.className = "message-content";

  if (type === "user") {
    messageContent.textContent = content;
  } else {
    messageContent.innerHTML = content;
  }

  const messageMeta = document.createElement("div");
  messageMeta.className = "message-meta";
  messageMeta.textContent = new Date().toLocaleTimeString();

  messageContent.appendChild(messageMeta);
  messageDiv.appendChild(avatar);
  messageDiv.appendChild(messageContent);

  elements.chatMessages.appendChild(messageDiv);
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

  // Store message in state
  state.messages.push({
    type: type,
    content: content,
    data: data,
    timestamp: new Date().toISOString(),
  });

  saveSessionData();
}

function showLoading() {
  const loadingDiv = document.createElement("div");
  loadingDiv.className = "message bot";
  loadingDiv.id = "loading-message";

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.innerHTML = '<i class="fas fa-robot"></i>';

  const loadingContent = document.createElement("div");
  loadingContent.className = "message-content";
  loadingContent.innerHTML = `
        <div class="loading">
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
        </div>
    `;

  loadingDiv.appendChild(avatar);
  loadingDiv.appendChild(loadingContent);

  elements.chatMessages.appendChild(loadingDiv);
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

  return "loading-message";
}

function removeLoading(loadingId) {
  const loading = document.getElementById(loadingId);
  if (loading) {
    loading.remove();
  }
}

function selectPond(pond) {
  console.log(`🎯 Selecting pond: ${pond}`);

  // If selecting "all" (Federated), deselect everything else
  if (pond === "all") {
    state.currentPond = "all";
    const allPondOptions = document.querySelectorAll(".pond-option");
    allPondOptions.forEach((option) => {
      if (option.dataset.pond === "all") {
        option.classList.add("active");
        console.log(`  ✓ Activated: all (Federated)`);
      } else {
        option.classList.remove("active");
      }
    });
  } else {
    // Multi-select mode: toggle the clicked pond
    const clickedOption = document.querySelector(
      `.pond-option[data-pond="${pond}"]`,
    );
    if (!clickedOption) return;

    // Deselect "all" if selecting a specific pond
    const allOption = document.querySelector('.pond-option[data-pond="all"]');
    if (allOption) {
      allOption.classList.remove("active");
    }

    // Toggle the clicked pond
    if (clickedOption.classList.contains("active")) {
      clickedOption.classList.remove("active");
      console.log(`  ✗ Deactivated: ${pond}`);
    } else {
      clickedOption.classList.add("active");
      console.log(`  ✓ Activated: ${pond}`);
    }

    // Get all active ponds (excluding "all")
    const activePonds = Array.from(
      document.querySelectorAll('.pond-option.active:not([data-pond="all"])'),
    ).map((opt) => opt.dataset.pond);

    // If no ponds selected, revert to "all"
    if (activePonds.length === 0) {
      if (allOption) {
        allOption.classList.add("active");
        state.currentPond = "all";
        console.log(`  ↩ Reverted to: all (Federated)`);
      }
    } else {
      // Store array of selected ponds
      state.currentPond = activePonds.length === 1 ? activePonds[0] : "all";
      state.selectedPonds = activePonds;
      console.log(`  📊 Selected ponds: ${activePonds.join(", ")}`);
    }
  }

  // Update placeholder
  const pondNames = {
    all: "Ask me about weather, tides, climate, or marine data...",
    atmospheric: "Ask about weather, alerts, forecasts...",
    oceanic: "Ask about tides, currents, water levels...",
    buoy: "Ask about marine buoy observations...",
    climate: "Ask about historical climate data...",
    archive: "Ask about archived environmental data...",
  };

  elements.chatInput.placeholder = pondNames[pond] || pondNames["all"];

  console.log(`Selected pond: ${pond}`);
}

function toggleTheme() {
  const currentTheme = document.body.dataset.theme;
  const newTheme = currentTheme === "dark" ? "light" : "dark";

  document.body.dataset.theme = newTheme;

  // Update icon
  const icon = elements.themeToggle.querySelector("i");
  icon.className = newTheme === "dark" ? "fas fa-sun" : "fas fa-moon";

  // Save preference
  localStorage.setItem("theme", newTheme);
}

function updateSessionStats() {
  elements.queryCount.textContent = state.queryCount;
  elements.dataCount.textContent = state.dataCount;
}

function saveSessionData() {
  const sessionData = {
    queryCount: state.queryCount,
    dataCount: state.dataCount,
    pondsQueried: Array.from(state.pondsQueried),
    currentPond: state.currentPond,
    timestamp: new Date().toISOString(),
  };

  localStorage.setItem("noaa_session", JSON.stringify(sessionData));
}

function loadSessionData() {
  const saved = localStorage.getItem("noaa_session");
  if (saved) {
    try {
      const sessionData = JSON.parse(saved);

      // Check if session is from today
      const sessionDate = new Date(sessionData.timestamp);
      const today = new Date();

      if (sessionDate.toDateString() === today.toDateString()) {
        state.queryCount = sessionData.queryCount || 0;
        state.dataCount = sessionData.dataCount || 0;
        state.pondsQueried = new Set(sessionData.pondsQueried || []);
        state.currentPond = sessionData.currentPond || "all";

        updateSessionStats();
        selectPond(state.currentPond);
      }
    } catch (e) {
      console.error("Error loading session data:", e);
    }
  }

  // Load theme preference
  const savedTheme = localStorage.getItem("theme");
  if (savedTheme) {
    document.body.dataset.theme = savedTheme;
    const icon = elements.themeToggle.querySelector("i");
    icon.className = savedTheme === "dark" ? "fas fa-sun" : "fas fa-moon";
  }
}

async function loadAvailablePonds() {
  let pondsData = null;

  try {
    console.log("Loading available ponds from backend...");

    const response = await fetch(
      `${CONFIG.API_BASE_URL}${CONFIG.PLAINTEXT_ENDPOINT}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: "get_ponds_metadata",
        }),
      },
    );

    if (response.ok) {
      let data = await response.json();

      // Unwrap nested data structure if present
      if (data.data) {
        data = data.data;
      }

      if (data.ponds) {
        pondsData = data.ponds;
        console.log(
          `✓ Loaded ${data.total_ponds || Object.keys(data.ponds).length} data ponds from API:`,
          Object.keys(data.ponds),
        );
      }
    } else {
      console.warn(
        "Could not fetch pond metadata from API, using fallback data",
      );
    }
  } catch (error) {
    console.warn("Error loading ponds metadata from API:", error);
  }

  // Use fallback data if API failed
  if (!pondsData) {
    console.log("Using fallback pond data");
    pondsData = FALLBACK_PONDS;
  }

  // Always update UI with either API data or fallback data
  state.availablePonds = pondsData;
  console.log(
    `✓ Using ${Object.keys(pondsData).length} data ponds:`,
    Object.keys(pondsData),
  );

  // Update pond selector UI dynamically
  updatePondSelector(pondsData);

  // Update pond-to-service mapping
  updatePondServiceMapping(pondsData);
}

function updatePondSelector(ponds) {
  const pondSelectorContainer = document.querySelector(".pond-selector");
  if (!pondSelectorContainer) {
    console.warn("Pond selector container not found");
    return;
  }

  // Keep the "all" option, update the rest
  const allOption = pondSelectorContainer.querySelector('[data-pond="all"]');

  // Clear existing pond options (keep "all")
  const existingOptions = pondSelectorContainer.querySelectorAll(
    '.pond-option:not([data-pond="all"])',
  );
  existingOptions.forEach((opt) => opt.remove());

  // Icon mapping for ponds
  const pondIcons = {
    atmospheric: "fa-cloud-sun-rain",
    oceanic: "fa-water",
    buoy: "fa-life-ring",
    climate: "fa-chart-line",
    terrestrial: "fa-globe-americas",
    spatial: "fa-map-marked-alt",
    archive: "fa-archive",
  };

  // Add new pond options dynamically
  Object.keys(ponds).forEach((pondName) => {
    const pond = ponds[pondName];
    const pondOption = document.createElement("div");
    pondOption.className = "pond-option";
    pondOption.setAttribute("data-pond", pondName);

    const icon = pondIcons[pondName] || "fa-database";
    const displayName = pondName.charAt(0).toUpperCase() + pondName.slice(1);
    const tooltipText = pond.description || `${displayName} data source`;

    // Set tooltip attribute
    pondOption.setAttribute("data-tooltip", tooltipText);

    pondOption.innerHTML = `
      <i class="fas ${icon}"></i>
      <div style="flex: 1">
        <strong>${displayName}</strong>
      </div>
    `;

    pondSelectorContainer.appendChild(pondOption);
  });

  // Re-attach event listeners to new pond options
  setupPondSelectors();

  console.log("✓ Pond selector updated with dynamic data");
}

function updatePondServiceMapping(ponds) {
  // Update CONFIG.POND_TO_SERVICE based on pond names
  // This is a simple mapping - could be enhanced with actual service info from backend
  const serviceMap = {
    atmospheric: "nws",
    oceanic: "tides",
    buoy: "ndbc",
    climate: "cdo",
    terrestrial: "soil",
    spatial: "gis",
    archive: "ncei",
  };

  Object.keys(ponds).forEach((pondName) => {
    if (!CONFIG.POND_TO_SERVICE[pondName] && serviceMap[pondName]) {
      CONFIG.POND_TO_SERVICE[pondName] = serviceMap[pondName];
    }
  });

  console.log("✓ Pond-to-service mapping updated:", CONFIG.POND_TO_SERVICE);

  // Also populate endpoints panel
  populateEndpointsPanel(ponds);
  updateServiceStatus(ponds);
}

function populateEndpointsPanel(ponds) {
  const container = document.getElementById("endpoints-container");
  if (!container) {
    console.warn("Endpoints container not found");
    return;
  }

  let html = '<div style="font-size: 11px;">';
  let totalEndpoints = 0;

  // Icon mapping for different services
  const serviceIcons = {
    nws: "fa-cloud-sun-rain",
    tides: "fa-water",
    ndbc: "fa-life-ring",
    cdo: "fa-chart-line",
    drought: "fa-tint-slash",
    soil: "fa-seedling",
  };

  // Group endpoints by pond
  Object.keys(ponds).forEach((pondName) => {
    const pond = ponds[pondName];
    const endpoints = pond.endpoints || [];

    if (endpoints.length === 0) return;

    totalEndpoints += endpoints.length;

    // Pond header
    html += `
      <div style="margin: 10px 0; padding: 8px; background: rgba(255,255,255,0.05); border-radius: 4px;">
        <div style="font-weight: bold; margin-bottom: 5px; display: flex; justify-content: space-between; align-items: center;">
          <span><i class="fas fa-database"></i> ${pondName.charAt(0).toUpperCase() + pondName.slice(1)}</span>
          <span style="font-size: 9px; opacity: 0.7;">${endpoints.length} endpoint${endpoints.length > 1 ? "s" : ""}</span>
        </div>
    `;

    // List endpoints
    endpoints.forEach((endpoint) => {
      const icon = serviceIcons[endpoint.service] || "fa-plug";
      const tokenBadge = endpoint.requires_token
        ? '<span style="background: #ff9800; color: white; padding: 1px 4px; border-radius: 3px; font-size: 8px; margin-left: 5px;">TOKEN</span>'
        : "";

      html += `
        <div style="margin: 5px 0; padding: 8px 10px; background: rgba(0,0,0,0.2); border-radius: 3px; cursor: pointer;"
             class="endpoint-item"
             data-pond="${pondName}"
             data-service="${endpoint.service}"
             data-tooltip="${endpoint.description}">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="flex: 1;">
              <i class="fas ${icon}" style="margin-right: 5px; opacity: 0.7;"></i>
              <strong>${endpoint.name}</strong>
              ${tokenBadge}
            </div>
            <div style="font-size: 9px; opacity: 0.6; color: #0066cc;">
              <i class="fas fa-play-circle"></i> Query
            </div>
          </div>
        </div>
      `;
    });

    html += "</div>";
  });

  if (totalEndpoints === 0) {
    html =
      '<div style="padding: 10px; opacity: 0.7; font-size: 11px;">No endpoints available</div>';
  }

  html += "</div>";
  container.innerHTML = html;

  console.log(
    `✓ Populated ${totalEndpoints} endpoints across ${Object.keys(ponds).length} ponds`,
  );

  // Update total count in service status
  const countElement = document.getElementById("total-endpoints-count");
  if (countElement) {
    countElement.textContent = totalEndpoints;
  }

  // Add click handlers to endpoint items
  document.querySelectorAll(".endpoint-item").forEach((item) => {
    item.addEventListener("click", function () {
      const pond = this.getAttribute("data-pond");
      const service = this.getAttribute("data-service");
      const endpointName = this.querySelector("strong").textContent;
      console.log(`Endpoint clicked: ${pond} - ${service} - ${endpointName}`);

      // Query the endpoint directly
      queryEndpointDirectly(pond, service, endpointName);
    });
  });

  console.log(
    `✓ Populated ${totalEndpoints} endpoints across ${Object.keys(ponds).length} ponds`,
  );
}

function updateServiceStatus(ponds) {
  const container = document.getElementById("services-status-container");
  if (!container) {
    console.warn("Service status container not found");
    return;
  }

  // Count services and endpoints
  const serviceMap = {};
  let totalEndpoints = 0;
  let totalPonds = 0;

  Object.keys(ponds).forEach((pondName) => {
    const pond = ponds[pondName];
    const endpoints = pond.endpoints || [];

    if (endpoints.length > 0) {
      totalPonds++;
      totalEndpoints += endpoints.length;

      endpoints.forEach((endpoint) => {
        const serviceName = endpoint.service || "unknown";
        if (!serviceMap[serviceName]) {
          serviceMap[serviceName] = {
            name: serviceName,
            endpoints: 0,
            ponds: new Set(),
          };
        }
        serviceMap[serviceName].endpoints++;
        serviceMap[serviceName].ponds.add(pondName);
      });
    }
  });

  // Build HTML
  let html = '<div style="font-size: 10px; line-height: 1.6;">';

  // Summary
  html += `
    <div style="background: rgba(0, 102, 204, 0.1); padding: 8px; border-radius: 6px; margin-bottom: 10px;">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <div style="font-weight: 600; color: var(--primary-color);">${totalPonds} Data Sources</div>
          <div style="opacity: 0.7; font-size: 9px;">${totalEndpoints} Total Endpoints</div>
        </div>
        <i class="fas fa-check-circle" style="color: var(--success-color); font-size: 20px;"></i>
      </div>
    </div>
  `;

  // List each service
  Object.values(serviceMap).forEach((service) => {
    const serviceName = service.name.toUpperCase();
    const pondList = Array.from(service.ponds).join(", ");

    html += `
      <div style="display: flex; justify-content: space-between; margin: 5px 0; padding: 5px; background: rgba(255,255,255,0.03); border-radius: 4px;">
        <div style="flex: 1;">
          <div style="font-weight: 600;">${serviceName}</div>
          <div style="opacity: 0.6; font-size: 8px;">${service.endpoints} endpoint${service.endpoints > 1 ? "s" : ""}</div>
        </div>
        <span class="badge badge-success" style="padding: 2px 6px; font-size: 8px;">✓ Active</span>
      </div>
    `;
  });

  html += "</div>";
  container.innerHTML = html;

  console.log(
    `✓ Service status updated: ${Object.keys(serviceMap).length} services, ${totalEndpoints} endpoints across ${totalPonds} ponds`,
  );
}

async function queryEndpointDirectly(pond, service, endpointName) {
  console.log(`Querying endpoint: ${pond}/${service}/${endpointName}`);

  // Add user message
  addMessage("user", `Query endpoint: ${endpointName} (${pond})`);

  // Show loading
  state.isProcessing = true;
  const loadingId = showLoading();

  try {
    // Query via passthrough API
    const response = await fetch(
      `${CONFIG.API_BASE_URL}${CONFIG.PASSTHROUGH_ENDPOINT}?service=${service}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }

    const rawData = await response.json();
    const contentType = response.headers.get("content-type");

    // Determine data format
    let dataFormat = "JSON";
    if (contentType && contentType.includes("text/csv")) {
      dataFormat = "CSV";
    } else if (contentType && contentType.includes("text/plain")) {
      dataFormat = "Plain Text";
    }

    removeLoading(loadingId);

    // Build response message
    let messageHTML = "<div>";
    messageHTML += `<h4><i class="fas fa-plug"></i> Endpoint Query Result</h4>`;
    messageHTML += `<div style="margin: 10px 0; padding: 10px; background: rgba(0,102,204,0.1); border-radius: 6px;">`;
    messageHTML += `<strong>Endpoint:</strong> ${endpointName}<br>`;
    messageHTML += `<strong>Service:</strong> ${service}<br>`;
    messageHTML += `<strong>Pond:</strong> ${pond}<br>`;
    messageHTML += `<strong>Format:</strong> ${dataFormat}`;
    messageHTML += `</div>`;

    // Show data preview
    messageHTML += `<div style="margin: 10px 0;">`;
    messageHTML += `<strong><i class="fas fa-database"></i> Raw Data Preview:</strong>`;
    messageHTML += `<pre style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 4px; overflow-x: auto; max-height: 200px; font-size: 10px;">${JSON.stringify(rawData, null, 2).substring(0, 1000)}${JSON.stringify(rawData, null, 2).length > 1000 ? "..." : ""}</pre>`;
    messageHTML += `</div>`;

    // Query gold layer data
    messageHTML += `<div style="margin: 10px 0;">`;
    messageHTML += `<strong><i class="fas fa-gem"></i> Gold Layer Data:</strong>`;
    messageHTML += `<div style="padding: 10px; background: rgba(255,193,7,0.1); border-radius: 4px; font-size: 11px;">`;

    try {
      // Query Athena for gold data
      const goldQuery = `SELECT * FROM noaa_gold_dev.${pond}_aggregated LIMIT 10`;
      messageHTML += `<div style="opacity: 0.7; margin-bottom: 5px;">Query: <code style="font-size: 10px;">${goldQuery}</code></div>`;
      messageHTML += `<div style="opacity: 0.7;">Status: Gold layer data available via Athena</div>`;
      messageHTML += `<div style="margin-top: 5px;"><a href="https://console.aws.amazon.com/athena/home?region=us-east-1#query" target="_blank" style="color: #ffc107;">→ Open in Athena Console</a></div>`;
    } catch (e) {
      messageHTML += `<div style="opacity: 0.7;">Gold layer not yet available for this pond</div>`;
    }

    messageHTML += `</div></div>`;

    // Action buttons
    messageHTML += `
      <div class="action-buttons">
        <button class="action-btn" onclick="viewRawData(${state.messages.length})">
          <i class="fas fa-code"></i> View Full Raw Data
        </button>
        <button class="action-btn" onclick="exportData(${state.messages.length})">
          <i class="fas fa-download"></i> Export
        </button>
      </div>
    `;

    messageHTML += "</div>";

    const messageData = {
      response: rawData,
      endpoint: endpointName,
      service: service,
      pond: pond,
      timestamp: new Date().toISOString(),
    };

    addMessage("bot", messageHTML, messageData);

    state.queryCount++;
    updateSessionStats();
  } catch (error) {
    removeLoading(loadingId);

    let errorHTML = "<div>";
    errorHTML += `<h4><i class="fas fa-exclamation-triangle"></i> Endpoint Query Failed</h4>`;
    errorHTML += `<div style="color: #f44336; padding: 10px; background: rgba(244,67,54,0.1); border-radius: 6px;">`;
    errorHTML += `<strong>Error:</strong> ${error.message}<br>`;
    errorHTML += `<strong>Endpoint:</strong> ${endpointName}<br>`;
    errorHTML += `<strong>Service:</strong> ${service}`;
    errorHTML += `</div>`;
    errorHTML += `<div style="margin-top: 10px; opacity: 0.7; font-size: 11px;">`;
    errorHTML += `This endpoint may require authentication, have rate limits, or be temporarily unavailable.`;
    errorHTML += `</div></div>`;

    addMessage("bot", errorHTML);

    console.error("Endpoint query failed:", error);
  } finally {
    state.isProcessing = false;
  }
}

function setupPondSelectors() {
  // Set up click handlers for pond options
  const pondOptions = document.querySelectorAll(".pond-option");
  console.log(`✓ Setting up ${pondOptions.length} pond selectors`);

  if (pondOptions.length === 0) {
    console.error("❌ NO pond options found!");
    return;
  }

  pondOptions.forEach((option, index) => {
    const pond = option.getAttribute("data-pond");
    console.log(`  Pond ${index + 1}: ${pond}`);

    option.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      const pondValue = this.getAttribute("data-pond");
      console.log(`🖱️ Pond clicked: ${pondValue}`);
      selectPond(pondValue);
    });
  });
}

// Toggle collapsible sections
function toggleSection(headerElement) {
  const section = headerElement.nextElementSibling;
  const toggleIcon = headerElement.querySelector(".toggle-icon");

  if (!section) {
    console.warn("No section found for header", headerElement);
    return;
  }

  console.log("Toggling section:", section.id || "unnamed section");

  // Toggle collapsed state
  if (section.classList.contains("collapsed")) {
    // Expand
    section.classList.remove("collapsed");
    headerElement.classList.remove("collapsed");
    section.style.maxHeight = section.scrollHeight + "px";

    // Rotate icon
    if (toggleIcon) {
      toggleIcon.style.transform = "rotate(0deg)";
    }
  } else {
    // Collapse
    section.classList.add("collapsed");
    headerElement.classList.add("collapsed");
    section.style.maxHeight = "0";

    // Rotate icon
    if (toggleIcon) {
      toggleIcon.style.transform = "rotate(-90deg)";
    }
  }
}

// Export for backward compatibility
window.toggleSection = toggleSection;

// Global functions for action buttons
window.viewRawData = function (messageIndex) {
  const message = state.messages[messageIndex];
  if (message && message.data) {
    const jsonWindow = window.open("", "_blank");
    jsonWindow.document.write("<html><head><title>Raw Data</title>");
    jsonWindow.document.write(
      "<style>body { font-family: monospace; background: #1e1e1e; color: #d4d4d4; padding: 20px; } pre { white-space: pre-wrap; word-wrap: break-word; }</style>",
    );
    jsonWindow.document.write("</head><body>");
    jsonWindow.document.write("<h2>Raw API Response</h2>");
    jsonWindow.document.write(
      "<pre>" + JSON.stringify(message.data.response, null, 2) + "</pre>",
    );
    jsonWindow.document.write("</body></html>");
    jsonWindow.document.close();
  }
};

window.exportData = function (messageIndex) {
  const message = state.messages[messageIndex];
  if (message && message.data) {
    const dataStr = JSON.stringify(message.data.response, null, 2);
    const dataBlob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `noaa-data-${Date.now()}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }
};

// Utility functions
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Log initialization
console.log("NOAA Data Lake Chatbot initialized");
console.log("Configuration:", CONFIG);
