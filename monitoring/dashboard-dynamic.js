// NOAA Dashboard Dynamic Data Loader
// Fetches real metrics from AWS backend instead of hardcoded data

const METRICS_API_ENDPOINT =
  "https://ghew7mwudk326bla57wgqe5xxi0ymhjm.lambda-url.us-east-1.on.aws/metrics";

// Cache for API responses (30 second TTL for real-time data)
const apiCache = {
  data: {},
  timestamps: {},
  TTL: 30 * 1000, // 30 seconds for real-time updates
};

// ============================================================================
// Core API Functions
// ============================================================================

async function fetchMetrics(metricType, params = {}, forceRefresh = false) {
  const cacheKey = `${metricType}_${JSON.stringify(params)}`;

  // Check cache (unless force refresh requested)
  if (!forceRefresh && apiCache.data[cacheKey] && apiCache.timestamps[cacheKey]) {
    const age = Date.now() - apiCache.timestamps[cacheKey];
    if (age < apiCache.TTL) {
      console.log(`Using cached data for ${cacheKey} (age: ${Math.floor(age/1000)}s)`);
      return apiCache.data[cacheKey];
    }
  }

  if (forceRefresh) {
    console.log(`Force refreshing ${metricType}`);
  }
</text>


  // Build query string
  const queryParams = new URLSearchParams({
    metric_type: metricType,
    ...params,
  });

  try {
    console.log(`Fetching metrics: ${metricType}`, params);

    // Add timeout protection (60 seconds)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);

    const response = await fetch(`${METRICS_API_ENDPOINT}?${queryParams}`, {
      signal: controller.signal,
      headers: {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
      }
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();

    // Cache the response
    apiCache.data[cacheKey] = data;
    apiCache.timestamps[cacheKey] = Date.now();

    return data;
  } catch (error) {
    if (error.name === 'AbortError') {
      console.error(`Timeout fetching ${metricType} (60s)`);
      throw new Error(`Request timeout - try again in a moment`);
    }
    console.error(`Error fetching ${metricType}:`, error);
    throw error;
  }
}

// ============================================================================
// Modal Control Functions
// ============================================================================

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("active");
  }
}

// Close modal when clicking outside the content
window.onclick = function (event) {
  if (event.target.classList.contains("modal")) {
    event.target.classList.remove("active");
  }
};

// Close modal on ESC key
document.addEventListener("keydown", function (event) {
  if (event.key === "Escape") {
    const activeModal = document.querySelector(".modal.active");
    if (activeModal) {
      activeModal.classList.remove("active");
    }
  }
});

function showLoading(modalBodyId) {
  const modalBody = document.getElementById(modalBodyId);
  if (modalBody) {
    modalBody.innerHTML = `
            <div class="loading-container" style="text-align: center; padding: 60px 20px;">
                <div class="loading-spinner" style="
                    border: 4px solid rgba(255, 255, 255, 0.3);
                    border-top: 4px solid #4ecdc4;
                    border-radius: 50%;
                    width: 50px;
                    height: 50px;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 20px;
                "></div>
                <p style="color: rgba(255, 255, 255, 0.8); font-size: 1.1em;">Loading real-time data from AWS...</p>
            </div>
        `;
  }
}

function showError(modalBodyId, error) {
  const modalBody = document.getElementById(modalBodyId);
  if (modalBody) {
    modalBody.innerHTML = `
            <div class="error-container" style="text-align: center; padding: 60px 20px;">
                <div style="font-size: 4em; margin-bottom: 20px;">⚠️</div>
                <h3 style="color: #ff6b6b; margin-bottom: 15px;">Error Loading Data</h3>
                <p style="color: rgba(255, 255, 255, 0.8); margin-bottom: 10px;">${error.message || "Unknown error occurred"}</p>
                <button onclick="location.reload()" style="
                    background: #4ecdc4;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 1em;
                    margin-top: 20px;
                ">Reload Dashboard</button>
            </div>
        `;
  }
}

// ============================================================================
// Bronze Layer - Dynamic Data
// ============================================================================

async function showBronzeDetails() {
  const modalBody = document.getElementById("bronzeModalBody");
  showLoading("bronzeModalBody");
  document.getElementById("bronzeModal").classList.add("active");

  try {
    // Force refresh to show latest data
    const data = await fetchMetrics("bronze_layer", {}, true);

    let endpointsHtml = "";

    if (data.endpoints && data.endpoints.length > 0) {
      data.endpoints.forEach((endpoint) => {
        const config = endpoint.config || {};
        endpointsHtml += `
                    <div class="endpoint-card">
                        <h4>📡 ${endpoint.function_name}</h4>
                        <p><strong>Runtime:</strong> ${endpoint.runtime}</p>
                        <p><strong>Memory:</strong> ${endpoint.memory_mb} MB</p>
                        <p><strong>Timeout:</strong> ${endpoint.timeout_seconds}s</p>
                        <p><strong>Last Modified:</strong> ${endpoint.last_modified}</p>
                        ${config.API_ENDPOINT ? `<p><strong>API Endpoint:</strong> ${config.API_ENDPOINT}</p>` : ""}
                        ${config.FREQUENCY ? `<p><strong>Frequency:</strong> ${config.FREQUENCY}</p>` : ""}
                    </div>
                `;
      });
    }

    let samplesHtml = "";
    if (data.recent_samples && data.recent_samples.length > 0) {
      samplesHtml = "<h3>📄 Recent Data Samples</h3>";
      data.recent_samples.forEach((sample, idx) => {
        samplesHtml += `
                    <div class="endpoint-card">
                        <h4>Sample ${idx + 1} - ${sample.key.split("/").pop()}</h4>
                        <p><strong>Size:</strong> ${(sample.size / 1024).toFixed(2)} KB</p>
                        <p><strong>Last Modified:</strong> ${new Date(sample.last_modified).toLocaleString()}</p>
                        <div class="data-sample">${JSON.stringify(sample.data, null, 2)}</div>
                    </div>
                `;
      });
    }

    const storage = data.storage || {};
    const ingestion = data.ingestion_stats || {};

    modalBody.innerHTML = `
            <h3>📥 Raw API Data Ingestion - Bronze Layer</h3>
            <p>The Bronze layer stores raw, unprocessed data exactly as received from NOAA APIs.</p>

            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-label">Total Files</div>
                    <div class="stat-value">${storage.total_files?.toLocaleString() || "N/A"}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Storage Size</div>
                    <div class="stat-value">${storage.total_size_gb || "N/A"} GB</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Avg File Size</div>
                    <div class="stat-value">${storage.avg_file_size_kb || "N/A"} KB</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Invocations (24h)</div>
                    <div class="stat-value">${ingestion.invocations_24h?.toLocaleString() || "N/A"}</div>
                </div>
            </div>

            <div class="metric-detail">
                <strong>S3 Location:</strong> ${storage.prefix || "N/A"}
                <div class="metric-source">Source: S3 ListObjects API</div>
            </div>

            ${
              ingestion.error_rate_percent !== undefined
                ? `
            <div class="metric-detail">
                <strong>Error Rate:</strong> ${ingestion.error_rate_percent}% (${ingestion.errors_24h || 0} errors in 24h)
                <div class="metric-source">Source: CloudWatch Lambda metrics</div>
            </div>
            `
                : ""
            }

            <h3>🔌 Active Ingestion Endpoints</h3>
            ${endpointsHtml || "<p>No endpoints found or data unavailable.</p>"}

            ${samplesHtml}
        `;
  modalBody.innerHTML = content;
} catch (error) {
  console.error("Error loading bronze details:", error);
  const errorMsg = error.message || "Failed to load Bronze layer data. The backend may be processing - please try again.";
  showError("bronzeModalBody", errorMsg);
}
}

// ============================================================================
// Silver Layer - Dynamic Data
// ============================================================================

async function showSilverDetails() {
  const modalBody = document.getElementById("silverModalBody");
  showLoading("silverModalBody");
  document.getElementById("silverModal").classList.add("active");

  try {
    // Force refresh to show latest data
    const data = await fetchMetrics("silver_layer", {}, true);

    const storage = data.storage || {};
    const processing = data.processing_stats || {};
    const quality = data.quality_metrics || {};

    let glueJobsHtml = "";
    if (Object.keys(processing).length > 0) {
      glueJobsHtml = "<h3>🔧 Glue ETL Jobs</h3>";
      for (const [jobName, metrics] of Object.entries(processing)) {
        const statusColor =
          metrics.last_run_state === "SUCCEEDED"
            ? "#2ecc71"
            : metrics.last_run_state === "RUNNING"
              ? "#f39c12"
              : "#e74c3c";
        glueJobsHtml += `
                    <div class="metric-detail">
                        <strong>${jobName}</strong>
                        <p><span style="color: ${statusColor};">●</span> Status: ${metrics.last_run_state || "Unknown"}</p>
                        ${metrics.execution_time_seconds ? `<p>⏱️ Execution Time: ${metrics.execution_time_seconds}s</p>` : ""}
                        ${metrics.last_run_started ? `<p>🕐 Last Run: ${new Date(metrics.last_run_started).toLocaleString()}</p>` : ""}
                        <div class="metric-source">Source: AWS Glue GetJobRuns API</div>
                    </div>
                `;
      }
    }

    let transformationsHtml = "";
    if (
      data.transformation_examples &&
      data.transformation_examples.length > 0
    ) {
      transformationsHtml = "<h3>🔄 Transformation Examples</h3>";
      data.transformation_examples.forEach((example) => {
        transformationsHtml += `
                    <div class="transformation-step">
                        <h4>Pond: ${example.pond}</h4>
                        <div class="before-after">
                            <div>
                                <h5>Before (Bronze)</h5>
                                <pre>${JSON.stringify(example.bronze, null, 2)}</pre>
                            </div>
                            <div>
                                <h5>After (Silver)</h5>
                                <pre>${JSON.stringify(example.silver, null, 2)}</pre>
                            </div>
                        </div>
                    </div>
                `;
      });
    }

    modalBody.innerHTML = `
            <h3>🔄 Data Processing & Validation Pipeline</h3>
            <p>The Silver layer applies quality checks, validation, and initial transformations to Bronze data.</p>

            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-label">Total Files</div>
                    <div class="stat-value">${storage.total_files?.toLocaleString() || "N/A"}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Storage Size</div>
                    <div class="stat-value">${storage.total_size_gb || "N/A"} GB</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Avg Quality Score</div>
                    <div class="stat-value">${quality.atmospheric?.avg_quality?.toFixed(1) || "N/A"}%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Active Jobs</div>
                    <div class="stat-value">${Object.keys(processing).length}</div>
                </div>
            </div>

            <div class="metric-detail">
                <strong>S3 Location:</strong> ${storage.prefix || "N/A"}
                <div class="metric-source">Source: S3 ListObjects API</div>
            </div>

            ${glueJobsHtml}
            ${transformationsHtml}

            <div class="section-divider"></div>

            <h3>📊 Processing Metrics</h3>
            <p>Glue ETL jobs process Bronze data through validation, cleaning, and enrichment steps.</p>
            <div class="metric-source">Source: AWS Glue API + CloudWatch Metrics</div>
        `;
  modalBody.innerHTML = content;
} catch (error) {
  console.error("Error loading silver details:", error);
  const errorMsg = error.message || "Failed to load Silver layer data. The backend may be processing - please try again.";
  showError("silverModalBody", errorMsg);
}
}

// ============================================================================
// Gold Layer - Dynamic Data
// ============================================================================

async function showGoldDetails() {
  const modalBody = document.getElementById("goldModalBody");
  showLoading("goldModalBody");
  document.getElementById("goldModal").classList.add("active");

  try {
    // Force refresh to show latest data
    const data = await fetchMetrics("gold_layer", {}, true);

    const storage = data.storage || {};
    const queryPerf = data.query_performance || {};
    const tables = data.tables || [];

    let tablesHtml = "";
    if (tables.length > 0) {
      tablesHtml = "<h3>📊 Athena Tables</h3>";
      tables.forEach((table) => {
        const formatName = table.output_format?.includes("Parquet")
          ? "Parquet"
          : table.output_format?.includes("Json")
            ? "JSON"
            : "Other";
        tablesHtml += `
                    <div class="endpoint-card">
                        <h4>📋 ${table.name}</h4>
                        <p><strong>Format:</strong> ${formatName}</p>
                        <p><strong>Columns:</strong> ${table.columns}</p>
                        <p><strong>Partitions:</strong> ${table.partitions.join(", ") || "None"}</p>
                        <p><strong>Location:</strong> ${table.location}</p>
                    </div>
                `;
      });
    }

    modalBody.innerHTML = `
            <h3>💎 Analytics-Ready Data Optimization</h3>
            <p>The Gold layer converts Silver data into highly optimized Parquet format for fast queries and reduced costs.</p>

            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-label">Total Files</div>
                    <div class="stat-value">${storage.total_files?.toLocaleString() || "N/A"}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Storage Size</div>
                    <div class="stat-value">${storage.total_size_gb || "N/A"} GB</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Compression Ratio</div>
                    <div class="stat-value">${data.compression_ratio || "N/A"}:1</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Athena Tables</div>
                    <div class="stat-value">${tables.length}</div>
                </div>
            </div>

            <div class="metric-detail">
                <strong>S3 Location:</strong> ${storage.prefix || "N/A"}
                <div class="metric-source">Source: S3 ListObjects API</div>
            </div>

            ${
              queryPerf.avg_execution_time_ms
                ? `
            <div class="metric-detail">
                <strong>Avg Query Time:</strong> ${(queryPerf.avg_execution_time_ms / 1000).toFixed(2)}s
                <br><strong>Data Scanned (24h):</strong> ${queryPerf.data_scanned_24h_gb || "N/A"} GB
                <div class="metric-source">Source: CloudWatch Athena metrics</div>
            </div>
            `
                : ""
            }

            ${tablesHtml}

            <div class="section-divider"></div>

            <h3>📈 Query Performance</h3>
            <p>Parquet columnar format with partitioning enables 10-50x faster queries compared to JSON.</p>
            <div class="metric-source">Source: AWS Glue Data Catalog + Athena CloudWatch Metrics</div>
        `;
  modalBody.innerHTML = content;
} catch (error) {
  console.error("Error loading gold details:", error);
  const errorMsg = error.message || "Failed to load Gold layer data. The backend may be processing - please try again in a moment.";
  showError("goldModalBody", errorMsg);
}
}

// ============================================================================
// Pond Details - Dynamic Data
// ============================================================================

async function showPondDetails(pondName) {
  const modalBody = document.getElementById("pondModalBody");
  const modalTitle = document.getElementById("pondModalTitle");

  showLoading("pondModalBody");
  modalTitle.textContent = `${pondName.charAt(0).toUpperCase() + pondName.slice(1)} Pond Details`;
  document.getElementById("pondModal").classList.add("active");

  try {
    const data = await fetchMetrics("pond_details", { pond_name: pondName });

    const metrics = data.metrics || {};
    const endpoints = data.endpoints || [];
    const recentData = data.recent_data || [];
    const schemas = data.athena_tables || [];
    const recordCounts = metrics.record_counts || {};

    const pondIcons = {
      atmospheric: "🌤️",
      oceanic: "🌊",
      buoy: "⚓",
      climate: "🌡️",
      spatial: "🗺️",
      terrestrial: "🌍",
    };

    let endpointsHtml = "";
    if (endpoints.length > 0) {
      endpointsHtml = "<h3>🔌 Ingestion Endpoints</h3>";
      endpoints.forEach((endpoint) => {
        endpointsHtml += `
                    <div class="endpoint-card">
                        <h4>${endpoint.function_name}</h4>
                        <p><strong>Description:</strong> ${endpoint.description || "N/A"}</p>
                        <p><strong>Runtime:</strong> ${endpoint.runtime}</p>
                        <p><strong>Timeout:</strong> ${endpoint.timeout}s</p>
                        <p><strong>Memory:</strong> ${endpoint.memory} MB</p>
                        ${endpoint.api_endpoint ? `<p><strong>API:</strong> ${endpoint.api_endpoint}</p>` : ""}
                        ${endpoint.frequency ? `<p><strong>Frequency:</strong> ${endpoint.frequency}</p>` : ""}
                        <p><strong>Last Modified:</strong> ${new Date(endpoint.last_modified).toLocaleString()}</p>
                    </div>
                `;
      });
    }

    let samplesHtml = "";
    if (recentData.length > 0) {
      samplesHtml = "<h3>📄 Recent Data Samples</h3>";
      recentData.forEach((sample, idx) => {
        samplesHtml += `
                    <div class="endpoint-card">
                        <h4>Sample ${idx + 1}</h4>
                        <p><strong>Key:</strong> ${sample.key}</p>
                        <p><strong>Size:</strong> ${(sample.size / 1024).toFixed(2)} KB</p>
                        <p><strong>Time:</strong> ${new Date(sample.last_modified).toLocaleString()}</p>
                        <div class="data-sample">${JSON.stringify(sample.data, null, 2)}</div>
                    </div>
                `;
      });
    }

    let schemasHtml = "";
    if (schemas.length > 0) {
      schemasHtml = "<h3>📊 Athena Table Schemas</h3>";
      schemas.forEach((schema) => {
        schemasHtml += `
                    <div class="endpoint-card">
                        <h4>${schema.table_name}</h4>
                        <p><strong>Columns:</strong> ${schema.columns.length}</p>
                        <ul style="margin-left: 20px; margin-top: 10px;">
                            ${schema.columns
                              .slice(0, 10)
                              .map(
                                (col) =>
                                  `<li><code>${col.name}</code>: ${col.type}</li>`,
                              )
                              .join("")}
                            ${schema.columns.length > 10 ? `<li><em>... and ${schema.columns.length - 10} more</em></li>` : ""}
                        </ul>
                    </div>
                `;
      });
    }

    modalBody.innerHTML = `
            <h3>${pondIcons[pondName] || "📊"} ${pondName.charAt(0).toUpperCase() + pondName.slice(1)} Pond</h3>
            <p>${data.pond_name} data pond with real-time metrics from AWS.</p>

            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-label">Records (24h)</div>
                    <div class="stat-value">${recordCounts.records_24h?.toLocaleString() || "N/A"}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Records (30d)</div>
                    <div class="stat-value">${recordCounts.total_30d?.toLocaleString() || "N/A"}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Bronze Storage</div>
                    <div class="stat-value">${metrics.bronze?.total_size_gb || "N/A"} GB</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Gold Storage</div>
                    <div class="stat-value">${metrics.gold?.total_size_gb || "N/A"} GB</div>
                </div>
            </div>

            ${endpointsHtml}
            ${samplesHtml}
            ${schemasHtml}

            <div class="metric-source">Source: Real-time data from AWS Lambda, S3, Glue, and Athena</div>
        `;
  } catch (error) {
    console.error("Error loading pond details:", error);
    showError("pondModalBody", error);
  }
}

// ============================================================================
// Transformation Details - Dynamic Data
// ============================================================================

async function showAtmosphericTransformation() {
  await showTransformationDetails("atmospheric");
}

async function showOceanicTransformation() {
  await showTransformationDetails("oceanic");
}

async function showBuoyTransformation() {
  await showTransformationDetails("buoy");
}

async function showTransformationDetails(pondName) {
  const modalBody = document.getElementById("silverModalBody");
  showLoading("silverModalBody");
  document.getElementById("silverModal").classList.add("active");

  try {
    const data = await fetchMetrics("transformation_details", {
      pond_name: pondName,
    });

    const bronze = data.bronze_sample;
    const silver = data.silver_sample;
    const gold = data.gold_sample;
    const transformations = data.transformations_applied || [];

    let transformationsHtml = "";
    if (transformations.length > 0) {
      transformationsHtml = "<h3>🔧 Applied Transformations</h3>";
      transformations.forEach((t) => {
        transformationsHtml += `
                    <div class="metric-detail">
                        <strong>${t.job_name}</strong>
                        <p>${t.description || "ETL transformation job"}</p>
                        <p><strong>Script:</strong> ${t.script_location}</p>
                        <p><strong>Glue Version:</strong> ${t.glue_version}</p>
                    </div>
                `;
      });
    }

    modalBody.innerHTML = `
            <h3>🔄 ${pondName.charAt(0).toUpperCase() + pondName.slice(1)} Transformation Pipeline</h3>
            <p>Real transformation examples showing how data flows from Bronze → Silver → Gold</p>

            ${
              bronze
                ? `
            <div class="transformation-step">
                <h4>🥉 Bronze Layer (Raw API Response)</h4>
                <div class="data-sample">${JSON.stringify(bronze, null, 2)}</div>
            </div>
            `
                : "<p>No Bronze sample available</p>"
            }

            ${
              silver
                ? `
            <div class="transformation-step">
                <h4>🥈 Silver Layer (Cleaned & Validated)</h4>
                <div class="data-sample">${JSON.stringify(silver, null, 2)}</div>
            </div>
            `
                : "<p>No Silver sample available</p>"
            }

            ${
              gold
                ? `
            <div class="transformation-step">
                <h4>🥇 Gold Layer (Analytics-Ready)</h4>
                <div class="data-sample">${JSON.stringify(gold, null, 2)}</div>
            </div>
            `
                : "<p>No Gold sample available</p>"
            }

            ${transformationsHtml}

            <div class="metric-source">Source: Real data from S3 and Athena queries</div>
        `;
  } catch (error) {
    console.error("Error loading transformation details:", error);
    showError("silverModalBody", error);
  }
}

// ============================================================================
// AI Metrics - Dynamic Data
// ============================================================================

async function showAIMetricsDetails() {
  const modalBody = document.getElementById("aiMetricsModalBody");
  showLoading("aiMetricsModalBody");
  document.getElementById("aiMetricsModal").classList.add("active");

  try {
    const data = await fetchMetrics("ai_metrics");

    const queryStats = data.query_stats || {};
    const performance = data.performance_metrics || {};
    const modelInfo = data.model_info || {};
    const costs = data.cost_metrics || {};

    modalBody.innerHTML = `
            <h3>🤖 AI Query System Performance Metrics</h3>
            <p>Real-time metrics from AWS Bedrock, Lambda, and Athena integration.</p>

            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-label">Queries Today</div>
                    <div class="stat-value">${queryStats.queries_today || "N/A"}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Avg Response Time</div>
                    <div class="stat-value">${queryStats.avg_duration_ms ? (queryStats.avg_duration_ms / 1000).toFixed(1) + "s" : "N/A"}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Success Rate</div>
                    <div class="stat-value">${queryStats.success_rate_percent?.toFixed(1) || "N/A"}%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Errors (24h)</div>
                    <div class="stat-value">${queryStats.errors_24h || "0"}</div>
                </div>
            </div>

            <div class="metric-detail">
                <strong>AI Model:</strong> ${modelInfo.model_id || "Claude 3.5 Sonnet"}
                <br><strong>Provider:</strong> AWS Bedrock
                <div class="metric-source">Source: Lambda CloudWatch metrics</div>
            </div>

            ${
              performance.avg_athena_queries
                ? `
            <div class="metric-detail">
                <strong>Avg Athena Queries per AI Request:</strong> ${performance.avg_athena_queries}
                <br><strong>Avg Data Scanned:</strong> ${performance.avg_data_scanned_gb || "N/A"} GB
                <div class="metric-source">Source: Athena CloudWatch metrics</div>
            </div>
            `
                : ""
            }

            ${
              costs.total_cost_24h
                ? `
            <div class="metric-detail">
                <strong>Estimated Cost (24h):</strong> $${costs.total_cost_24h.toFixed(2)}
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>Bedrock: $${costs.bedrock_cost?.toFixed(2) || "0.00"}</li>
                    <li>Athena: $${costs.athena_cost?.toFixed(2) || "0.00"}</li>
                    <li>Lambda: $${costs.lambda_cost?.toFixed(2) || "0.00"}</li>
                </ul>
                <div class="metric-source">Source: Calculated from CloudWatch usage metrics</div>
            </div>
            `
                : ""
            }

            <div class="section-divider"></div>

            <h3>📊 Query Breakdown</h3>
            <p>All metrics are pulled in real-time from CloudWatch, Lambda execution logs, and Bedrock usage data.</p>
            <div class="metric-source">Data refreshed every 5 minutes</div>
        `;
  } catch (error) {
    console.error("Error loading AI metrics:", error);
    showError("aiMetricsModalBody", error);
  }
}

// ============================================================================
// Overview Metrics - Dynamic Data
// ============================================================================

async function loadOverviewMetrics() {
  try {
    const data = await fetchMetrics("overview");

    // Update metric cards if they exist
    const elements = {
      totalRecords: document.querySelector('[data-metric="total-records"]'),
      activePonds: document.querySelector('[data-metric="active-ponds"]'),
      storageSize: document.querySelector('[data-metric="storage-size"]'),
      aiQueries: document.querySelector('[data-metric="ai-queries"]'),
    };

    if (elements.totalRecords) {
      elements.totalRecords.textContent =
        data.total_records_24h?.toLocaleString() || "N/A";
    }
    if (elements.activePonds) {
      elements.activePonds.textContent = data.active_ponds || "N/A";
    }
    if (elements.storageSize) {
      elements.storageSize.textContent = `${data.storage_gold_gb?.toFixed(1) || "N/A"} GB`;
    }
    if (elements.aiQueries) {
      elements.aiQueries.textContent =
        data.ai_queries_today?.toLocaleString() || "N/A";
    }

    console.log("Overview metrics loaded successfully");
    return true;
  } catch (error) {
    console.error("Error loading overview metrics:", error);
    return false;
  }
}

// ============================================================================
// Initialization
// ============================================================================

// Load overview metrics on page load
document.addEventListener("DOMContentLoaded", function () {
  console.log("Dashboard dynamic loader initialized");

  // Load overview metrics if elements exist
  if (document.querySelector('[data-metric="total-records"]')) {
    loadOverviewMetrics().catch((err) => {
      console.error("Failed to load overview metrics:", err);
    });
  }
});

// Add CSS animation for loading spinner
const style = document.createElement("style");
style.textContent = `
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
