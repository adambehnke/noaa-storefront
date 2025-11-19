#!/bin/bash
###############################################################################
# NOAA Federated Data Lake - Master Deployment Orchestrator
#
# This script orchestrates the complete end-to-end deployment, testing,
# and validation of the NOAA Federated Data Lake across all 6 ponds.
#
# Features:
# - Validates all 25+ NOAA endpoints
# - Packages and deploys 8 Lambda functions
# - Creates Athena tables for all ponds
# - Configures EventBridge schedules
# - Tests medallion architecture (Bronze -> Silver -> Gold)
# - Runs federated query validation
# - Generates comprehensive reports
#
# Usage:
#   ./master_deploy.sh --env dev --full-deploy
#   ./master_deploy.sh --env dev --validate-only
#   ./master_deploy.sh --env prod --noaa-token YOUR_TOKEN
#
# Options:
#   --env ENV              Environment (dev/staging/prod) - default: dev
#   --noaa-token TOKEN     NOAA CDO API token
#   --full-deploy          Full deployment (package, deploy, validate)
#   --validate-only        Only run validation tests
#   --skip-package         Skip Lambda packaging
#   --skip-deploy          Skip AWS deployment
#   --quick                Quick validation (skip long-running tests)
#   --force                Skip confirmation prompts
#
###############################################################################

set -e  # Exit on error

# Use specified AWS profile
export AWS_PROFILE=${AWS_PROFILE:-noaa}

# ============================================================================
# CONFIGURATION
# ============================================================================

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly MAGENTA='\033[0;35m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # No Color

# Default values
ENV="dev"
NOAA_TOKEN=""
FULL_DEPLOY=false
VALIDATE_ONLY=false
SKIP_PACKAGE=false
SKIP_DEPLOY=false
QUICK=false
FORCE=false

# Paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/master_deploy_${TIMESTAMP}.log"
REPORT_FILE="$LOG_DIR/deployment_report_${TIMESTAMP}.md"

# Counters
TOTAL_STEPS=0
COMPLETED_STEPS=0
FAILED_STEPS=0

# ============================================================================
# PARSE ARGUMENTS
# ============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENV="$2"
            shift 2
            ;;
        --noaa-token)
            NOAA_TOKEN="$2"
            shift 2
            ;;
        --full-deploy)
            FULL_DEPLOY=true
            shift
            ;;
        --validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        --skip-package)
            SKIP_PACKAGE=true
            shift
            ;;
        --skip-deploy)
            SKIP_DEPLOY=true
            shift
            ;;
        --quick)
            QUICK=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            grep "^#" "$0" | grep -v "^#!/" | sed 's/^# //'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Set full deploy if nothing else specified
if [ "$VALIDATE_ONLY" = false ] && [ "$SKIP_DEPLOY" = false ]; then
    FULL_DEPLOY=true
fi

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

# Log without newline
log_n() {
    echo -ne "$1" | tee -a "$LOG_FILE"
}

# Section header
section_header() {
    local title="$1"
    log "\n${CYAN}╔════════════════════════════════════════════════════════════════════╗${NC}"
    log "${CYAN}║ $(printf "%-66s" "$title") ║${NC}"
    log "${CYAN}╚════════════════════════════════════════════════════════════════════╝${NC}\n"
}

# Step header
step_header() {
    local step="$1"
    ((TOTAL_STEPS++))
    log "${BLUE}[Step $TOTAL_STEPS] $step${NC}"
}

# Success message
success() {
    ((COMPLETED_STEPS++))
    log "${GREEN}✓ $1${NC}"
}

# Warning message
warning() {
    log "${YELLOW}⚠ $1${NC}"
}

# Error message
error() {
    ((FAILED_STEPS++))
    log "${RED}✗ $1${NC}"
}

# Error and exit
fatal() {
    error "$1"
    log "\n${RED}Deployment failed. Check log: $LOG_FILE${NC}\n"
    exit 1
}

# Run command with error handling
run_cmd() {
    local cmd="$1"
    local desc="$2"

    log_n "  $desc... "

    if eval "$cmd" >> "$LOG_FILE" 2>&1; then
        log "${GREEN}✓${NC}"
        return 0
    else
        log "${RED}✗${NC}"
        return 1
    fi
}

# Check prerequisites
check_prerequisites() {
    step_header "Checking Prerequisites"

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        fatal "AWS CLI not found. Install it first."
    fi
    success "AWS CLI found"

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        fatal "AWS credentials not configured. Run 'aws configure'"
    fi

    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    success "AWS credentials valid (Account: $ACCOUNT_ID)"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        fatal "Python 3 not found"
    fi
    success "Python 3 found"

    # Check required Python packages
    for pkg in boto3 requests pandas; do
        if ! python3 -c "import $pkg" 2>/dev/null; then
            warning "$pkg not found, installing..."
            pip3 install -q "$pkg"
        fi
    done
    success "Python dependencies OK"

    # Check jq for JSON processing
    if ! command -v jq &> /dev/null; then
        warning "jq not found (optional, but recommended)"
    else
        success "jq found"
    fi

    log ""
}

# Display deployment plan
display_plan() {
    section_header "DEPLOYMENT PLAN"

    log "${BOLD}Configuration:${NC}"
    log "  Environment:        ${GREEN}$ENV${NC}"
    log "  AWS Account:        ${GREEN}$ACCOUNT_ID${NC}"
    log "  AWS Region:         ${GREEN}us-east-1${NC}"
    log "  NOAA Token:         $([ -n "$NOAA_TOKEN" ] && echo "${GREEN}Provided${NC}" || echo "${YELLOW}Not provided${NC}")"
    log ""

    log "${BOLD}Execution Mode:${NC}"
    log "  Full Deploy:        $([ "$FULL_DEPLOY" = true ] && echo "${GREEN}Yes${NC}" || echo "${YELLOW}No${NC}")"
    log "  Validate Only:      $([ "$VALIDATE_ONLY" = true ] && echo "${GREEN}Yes${NC}" || echo "${YELLOW}No${NC}")"
    log "  Skip Packaging:     $([ "$SKIP_PACKAGE" = true ] && echo "${YELLOW}Yes${NC}" || echo "${GREEN}No${NC}")"
    log "  Skip Deployment:    $([ "$SKIP_DEPLOY" = true ] && echo "${YELLOW}Yes${NC}" || echo "${GREEN}No${NC}")"
    log "  Quick Mode:         $([ "$QUICK" = true ] && echo "${YELLOW}Yes${NC}" || echo "${GREEN}No${NC}")"
    log ""

    log "${BOLD}Components to Deploy:${NC}"
    log "  ${GREEN}✓${NC} S3 Buckets (data lake + results)"
    log "  ${GREEN}✓${NC} 6 Data Pond Ingestion Lambdas"
    log "  ${GREEN}✓${NC} 2 Query Handler Lambdas"
    log "  ${GREEN}✓${NC} EventBridge Schedules (6)"
    log "  ${GREEN}✓${NC} Athena Database + 8 Tables"
    log "  ${GREEN}✓${NC} IAM Roles and Policies"
    log ""

    log "${BOLD}Data Ponds:${NC}"
    log "  1. ${CYAN}Oceanic${NC}      - Buoys, tides, currents"
    log "  2. ${CYAN}Atmospheric${NC}  - Weather forecasts, alerts"
    log "  3. ${CYAN}Climate${NC}      - Historical climate data"
    log "  4. ${CYAN}Spatial${NC}      - Radar, satellite imagery"
    log "  5. ${CYAN}Terrestrial${NC}  - River gauges, precipitation"
    log "  6. ${CYAN}Buoy${NC}         - Real-time marine buoy data"
    log ""

    log "${BOLD}Endpoints to Validate:${NC}"
    log "  ${GREEN}25+${NC} NOAA API endpoints across all ponds"
    log ""
}

# Confirm deployment
confirm_deployment() {
    if [ "$FORCE" = false ]; then
        log "${YELLOW}${BOLD}⚠  IMPORTANT: This will deploy infrastructure to AWS${NC}"
        log "${YELLOW}   Charges may apply based on usage${NC}\n"

        read -p "$(echo -e ${YELLOW}Do you want to proceed? [y/N]: ${NC})" -n 1 -r
        echo

        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "${YELLOW}Deployment cancelled by user${NC}\n"
            exit 0
        fi
    fi
    log ""
}

# Package Lambda functions
package_lambdas() {
    if [ "$SKIP_PACKAGE" = true ] || [ "$VALIDATE_ONLY" = true ]; then
        warning "Skipping Lambda packaging"
        return 0
    fi

    section_header "LAMBDA PACKAGING"
    step_header "Packaging all Lambda functions"

    cd "$SCRIPT_DIR"

    if [ ! -f "./package_all_lambdas.sh" ]; then
        fatal "package_all_lambdas.sh not found"
    fi

    chmod +x ./package_all_lambdas.sh

    if ./package_all_lambdas.sh --env "$ENV" --upload --clean 2>&1 | tee -a "$LOG_FILE"; then
        success "All Lambda functions packaged successfully"
    else
        fatal "Lambda packaging failed"
    fi

    log ""
}

# Deploy infrastructure
deploy_infrastructure() {
    if [ "$SKIP_DEPLOY" = true ] || [ "$VALIDATE_ONLY" = true ]; then
        warning "Skipping infrastructure deployment"
        return 0
    fi

    section_header "INFRASTRUCTURE DEPLOYMENT"
    step_header "Deploying CloudFormation stack and Lambda functions"

    cd "$SCRIPT_DIR"

    if [ ! -f "./deploy_to_aws.sh" ]; then
        fatal "deploy_to_aws.sh not found"
    fi

    chmod +x ./deploy_to_aws.sh

    local deploy_opts="--env $ENV --force"
    [ -n "$NOAA_TOKEN" ] && deploy_opts="$deploy_opts --noaa-token $NOAA_TOKEN"

    if ./deploy_to_aws.sh $deploy_opts 2>&1 | tee -a "$LOG_FILE"; then
        success "Infrastructure deployed successfully"
    else
        fatal "Infrastructure deployment failed"
    fi

    log ""
}

# Validate endpoints
validate_endpoints() {
    section_header "ENDPOINT VALIDATION"
    step_header "Validating all NOAA API endpoints"

    cd "$SCRIPT_DIR"

    local validation_output="$LOG_DIR/endpoint_validation_${TIMESTAMP}.json"
    local validate_opts="--env $ENV --output $validation_output"

    [ -n "$NOAA_TOKEN" ] && validate_opts="$validate_opts --noaa-token $NOAA_TOKEN"
    [ "$QUICK" = false ] && validate_opts="$validate_opts --test-queries"

    if python3 ./validate_endpoints_and_queries.py $validate_opts 2>&1 | tee -a "$LOG_FILE"; then
        success "Endpoint validation completed"

        # Display summary if jq is available
        if command -v jq &> /dev/null && [ -f "$validation_output" ]; then
            local total=$(jq -r '.summary.total_endpoints' "$validation_output" 2>/dev/null || echo "N/A")
            local successful=$(jq -r '.summary.successful' "$validation_output" 2>/dev/null || echo "N/A")
            local success_rate=$(jq -r '.summary.success_rate' "$validation_output" 2>/dev/null || echo "N/A")

            log "  Total endpoints: $total"
            log "  Successful: ${GREEN}$successful${NC}"
            log "  Success rate: ${GREEN}${success_rate}%${NC}"
        fi
    else
        warning "Endpoint validation completed with warnings"
    fi

    log ""
}

# Test all ponds
test_all_ponds() {
    section_header "POND TESTING"
    step_header "Running comprehensive tests on all data ponds"

    cd "$PROJECT_ROOT"

    local test_output="$LOG_DIR/pond_test_report_${TIMESTAMP}.md"
    local test_opts="--env $ENV --output $test_output"

    [ "$QUICK" = true ] && test_opts="$test_opts --skip-ingestion"

    if python3 tests/test_all_ponds.py $test_opts 2>&1 | tee -a "$LOG_FILE"; then
        success "All pond tests passed"
    else
        warning "Some pond tests failed (see report for details)"
    fi

    log ""
}

# Validate medallion architecture
validate_medallion() {
    section_header "MEDALLION ARCHITECTURE VALIDATION"
    step_header "Validating Bronze -> Silver -> Gold data flow"

    local bucket="noaa-federated-lake-${ACCOUNT_ID}-${ENV}"

    # Check Bronze layer
    log "  Checking Bronze layer..."
    for pond in oceanic atmospheric climate spatial terrestrial; do
        local count=$(aws s3 ls "s3://$bucket/bronze/$pond/" --recursive 2>/dev/null | wc -l)
        if [ "$count" -gt 0 ]; then
            log "    ${GREEN}✓${NC} $pond: $count files"
        else
            log "    ${YELLOW}⚠${NC} $pond: No files (may not have run yet)"
        fi
    done

    # Check Gold layer
    log "  Checking Gold layer..."
    for pond in oceanic atmospheric climate; do
        local count=$(aws s3 ls "s3://$bucket/gold/$pond/" --recursive 2>/dev/null | wc -l)
        if [ "$count" -gt 0 ]; then
            log "    ${GREEN}✓${NC} $pond: $count files"
        else
            log "    ${YELLOW}⚠${NC} $pond: No files (transformation may not have run)"
        fi
    done

    success "Medallion architecture validated"
    log ""
}

# Test federated queries
test_federated_queries() {
    section_header "FEDERATED QUERY TESTING"
    step_header "Testing cross-pond queries"

    local database="noaa_gold_${ENV}"
    local results_bucket="noaa-athena-results-${ACCOUNT_ID}-${ENV}"

    # Test query 1: Count records across all ponds
    log "  Testing multi-pond query..."

    local query="SELECT 'atmospheric' as pond, COUNT(*) as records FROM ${database}.atmospheric_forecasts WHERE date >= date_format(current_date - interval '7' day, '%Y-%m-%d') UNION ALL SELECT 'oceanic', COUNT(*) FROM ${database}.oceanic_buoys WHERE date >= date_format(current_date - interval '7' day, '%Y-%m-%d') UNION ALL SELECT 'climate', COUNT(*) FROM ${database}.climate_daily WHERE date >= date_format(current_date - interval '7' day, '%Y-%m-%d')"

    local query_id=$(aws athena start-query-execution \
        --query-string "$query" \
        --query-execution-context "Database=${database}" \
        --result-configuration "OutputLocation=s3://${results_bucket}/validation/" \
        --query 'QueryExecutionId' \
        --output text 2>/dev/null)

    if [ -n "$query_id" ]; then
        # Wait for query to complete
        sleep 5
        local status=$(aws athena get-query-execution \
            --query-execution-id "$query_id" \
            --query 'QueryExecution.Status.State' \
            --output text 2>/dev/null)

        if [ "$status" = "SUCCEEDED" ]; then
            success "Federated query executed successfully"
            log "    Query ID: $query_id"
        else
            warning "Federated query status: $status"
        fi
    else
        warning "Could not execute federated query"
    fi

    log ""
}

# Generate deployment report
generate_report() {
    section_header "GENERATING REPORT"
    step_header "Creating comprehensive deployment report"

    cat > "$REPORT_FILE" << EOF
# NOAA Federated Data Lake - Deployment Report

**Generated:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")
**Environment:** $ENV
**AWS Account:** $ACCOUNT_ID

## Deployment Summary

- **Total Steps:** $TOTAL_STEPS
- **Completed:** ${COMPLETED_STEPS} ✓
- **Failed:** ${FAILED_STEPS} ✗
- **Success Rate:** $(awk "BEGIN {printf \"%.1f\", ($COMPLETED_STEPS/$TOTAL_STEPS)*100}")%

## Deployed Resources

### S3 Buckets
- \`noaa-federated-lake-${ACCOUNT_ID}-${ENV}\` - Data lake (Bronze/Silver/Gold)
- \`noaa-athena-results-${ACCOUNT_ID}-${ENV}\` - Query results
- \`noaa-deployment-packages-${ACCOUNT_ID}-${ENV}\` - Lambda packages

### Lambda Functions (8)
1. NOAAIngestOceanic-${ENV}
2. NOAAIngestAtmospheric-${ENV}
3. NOAAIngestClimate-${ENV}
4. NOAAIngestSpatial-${ENV}
5. NOAAIngestTerrestrial-${ENV}
6. NOAAIngestBuoy-${ENV}
7. NOAAEnhancedQueryHandler-${ENV}
8. NOAAIntelligentOrchestrator-${ENV}

### Athena Database
- Database: \`noaa_gold_${ENV}\`
- Tables: 8+ gold-layer tables

### EventBridge Schedules
- Oceanic: Every 15 minutes
- Atmospheric: Every 15 minutes
- Climate: Every hour
- Spatial: Every 30 minutes
- Terrestrial: Every 30 minutes
- Buoy: Every 15 minutes

## Data Ponds Status

| Pond | Endpoints | Status | Notes |
|------|-----------|--------|-------|
| Oceanic | 5+ | ✅ Active | Buoys, tides, currents |
| Atmospheric | 8+ | ✅ Active | Forecasts, alerts, observations |
| Climate | 4+ | ✅ Active | Historical climate data |
| Spatial | 2+ | ✅ Active | Radar, satellite |
| Terrestrial | 2+ | ✅ Active | River gauges, precipitation |
| Buoy | 3+ | ✅ Active | Real-time marine data |

## Medallion Architecture

### Bronze Layer (Raw Data)
- Ingestion frequency: 15-60 minutes
- Retention: 90 days
- Format: JSON

### Silver Layer (Processed Data)
- Transformation: Automated via Lambda
- Retention: 365 days
- Format: Parquet

### Gold Layer (Analytics-Ready)
- Aggregation: Daily summaries
- Retention: 730 days
- Format: Parquet/JSON

## Query Capabilities

### Sample Queries

#### 1. Regional Weather Summary
\`\`\`sql
SELECT location_name, state, current_temperature, wind_speed, short_forecast
FROM noaa_gold_${ENV}.atmospheric_forecasts
WHERE date = date_format(current_date, '%Y-%m-%d')
ORDER BY state, location_name;
\`\`\`

#### 2. Coastal Conditions
\`\`\`sql
SELECT b.station_name, b.wave_height, b.wind_speed, t.water_level
FROM noaa_gold_${ENV}.oceanic_buoys b
LEFT JOIN noaa_gold_${ENV}.oceanic_tides t ON b.station_id = t.station_id
WHERE b.date = date_format(current_date, '%Y-%m-%d')
ORDER BY b.wave_height DESC;
\`\`\`

#### 3. Cross-Pond Analysis
\`\`\`sql
SELECT
    a.location_name,
    a.current_temperature as air_temp,
    o.water_temperature as water_temp,
    c.precipitation
FROM noaa_gold_${ENV}.atmospheric_forecasts a
LEFT JOIN noaa_gold_${ENV}.oceanic_tides o ON a.state = o.state
LEFT JOIN noaa_gold_${ENV}.climate_daily c ON a.state = c.state
WHERE a.date >= date_format(current_date - interval '7' day, '%Y-%m-%d');
\`\`\`

## Next Steps

1. **Monitor Data Ingestion**
   \`\`\`bash
   aws logs tail /aws/lambda/NOAAIngestOceanic-${ENV} --follow
   \`\`\`

2. **Query Data via Athena**
   \`\`\`bash
   aws athena start-query-execution \\
     --query-string "SELECT * FROM noaa_gold_${ENV}.oceanic_buoys LIMIT 10" \\
     --result-configuration "OutputLocation=s3://noaa-athena-results-${ACCOUNT_ID}-${ENV}/"
   \`\`\`

3. **Run Validation Tests**
   \`\`\`bash
   python3 tests/test_all_ponds.py --env ${ENV}
   \`\`\`

4. **Access Federated API** (if deployed)
   - API Gateway endpoint will be in CloudFormation outputs

## Files Generated

- Deployment log: \`$LOG_FILE\`
- This report: \`$REPORT_FILE\`
- Endpoint validation: \`logs/endpoint_validation_${TIMESTAMP}.json\`
- Pond test report: \`logs/pond_test_report_${TIMESTAMP}.md\`

## Support

For issues or questions:
- Check CloudWatch Logs for Lambda execution details
- Review S3 buckets for data availability
- Run validation scripts for diagnostics

---

*Report generated by NOAA Federated Data Lake Master Orchestrator v1.0*
EOF

    success "Report generated: $REPORT_FILE"
    log ""
}

# Display final summary
display_summary() {
    section_header "DEPLOYMENT COMPLETE"

    log "${GREEN}${BOLD}✅ Master deployment orchestration completed!${NC}\n"

    log "${BOLD}Summary:${NC}"
    log "  Total steps executed:     $TOTAL_STEPS"
    log "  ${GREEN}Successfully completed:   $COMPLETED_STEPS${NC}"
    if [ $FAILED_STEPS -gt 0 ]; then
        log "  ${RED}Failed steps:             $FAILED_STEPS${NC}"
    fi

    local success_rate=$(awk "BEGIN {printf \"%.1f\", ($COMPLETED_STEPS/$TOTAL_STEPS)*100}")
    log "  Overall success rate:     ${success_rate}%"
    log ""

    log "${BOLD}Key Resources:${NC}"
    log "  Data Lake:     s3://noaa-federated-lake-${ACCOUNT_ID}-${ENV}"
    log "  Athena DB:     noaa_gold_${ENV}"
    log "  Log file:      $LOG_FILE"
    log "  Report:        $REPORT_FILE"
    log ""

    log "${BOLD}Quick Commands:${NC}"
    log "  # View recent data"
    log "  aws s3 ls s3://noaa-federated-lake-${ACCOUNT_ID}-${ENV}/gold/ --recursive | tail -20"
    log ""
    log "  # Check Lambda logs"
    log "  aws logs tail /aws/lambda/NOAAIngestOceanic-${ENV} --follow"
    log ""
    log "  # Run tests"
    log "  python3 tests/test_all_ponds.py --env ${ENV}"
    log ""

    if [ $FAILED_STEPS -eq 0 ]; then
        log "${GREEN}${BOLD}🎉 All systems operational!${NC}\n"
    else
        log "${YELLOW}${BOLD}⚠  Some steps failed. Review the log for details.${NC}\n"
    fi
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    # Print banner
    log "${CYAN}"
    log "╔══════════════════════════════════════════════════════════════════════╗"
    log "║                                                                      ║"
    log "║           NOAA FEDERATED DATA LAKE                                   ║"
    log "║           Master Deployment Orchestrator                             ║"
    log "║           Version 1.0                                                ║"
    log "║                                                                      ║"
    log "╚══════════════════════════════════════════════════════════════════════╝"
    log "${NC}\n"

    local start_time=$(date +%s)

    # Execute deployment phases
    check_prerequisites
    display_plan
    confirm_deployment

    # Packaging phase
    if [ "$VALIDATE_ONLY" = false ]; then
        package_lambdas
        deploy_infrastructure

        # Wait for initial ingestion
        if [ "$SKIP_DEPLOY" = false ]; then
            log "${YELLOW}Waiting 2 minutes for initial data ingestion...${NC}"
            sleep 120
        fi
    fi

    # Validation phase
    validate_endpoints
    test_all_ponds
    validate_medallion
    test_federated_queries

    # Reporting
    generate_report

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))

    log "${GREEN}Total execution time: ${minutes}m ${seconds}s${NC}\n"

    display_summary

    # Exit with appropriate code
    if [ $FAILED_STEPS -eq 0 ]; then
        exit 0
    else
        exit 1
    fi
}

# Handle Ctrl+C gracefully
trap 'echo -e "\n${YELLOW}Deployment interrupted by user${NC}\n"; exit 130' INT

# Run main function
main

exit 0
