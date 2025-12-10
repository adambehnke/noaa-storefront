#!/bin/bash
###############################################################################
# NOAA Federated Data Lake - Account Migration Script
#
# This script facilitates migration of the NOAA Federated Data Lake to a new
# AWS account by:
#   - Detecting current AWS account
#   - Fixing hardcoded account references
#   - Updating configuration files
#   - Deploying infrastructure
#   - Verifying deployment
#   - Testing basic functionality
#
# Usage:
#   ./migrate_to_new_account.sh [OPTIONS]
#
# Options:
#   --env ENV              Environment (dev/staging/prod) - default: dev
#   --region REGION        AWS region - default: us-east-1
#   --skip-deploy          Only fix references, don't deploy
#   --deploy-only          Skip fixes, only deploy
#   --dry-run              Show what would be changed without changing
#   --force                Skip confirmations
#   --help                 Show this help message
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Python 3.9+
#   - Bash 4.0+
#
# Example:
#   # Full migration to new account in dev environment
#   ./migrate_to_new_account.sh --env dev
#
#   # Dry run to see what would change
#   ./migrate_to_new_account.sh --env dev --dry-run
#
###############################################################################

set -e  # Exit on error
set -o pipefail  # Exit on pipe failure

# ============================================================================
# COLORS AND FORMATTING
# ============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly MAGENTA='\033[0;35m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # No Color

# ============================================================================
# CONFIGURATION
# ============================================================================

# Default values
ENV="dev"
REGION="us-east-1"
SKIP_DEPLOY=false
DEPLOY_ONLY=false
DRY_RUN=false
FORCE=false

# Paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/migration_${TIMESTAMP}.log"
BACKUP_DIR="$PROJECT_ROOT/backups/migration_${TIMESTAMP}"

# Counters
TOTAL_FIXES=0
COMPLETED_FIXES=0
FAILED_FIXES=0

# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log_info() {
    log "${BLUE}ℹ${NC}  $1"
}

log_success() {
    log "${GREEN}✓${NC}  $1"
}

log_warning() {
    log "${YELLOW}⚠${NC}  $1"
}

log_error() {
    log "${RED}✗${NC}  $1"
}

log_header() {
    log ""
    log "${CYAN}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    log "${CYAN}${BOLD} $1${NC}"
    log "${CYAN}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    log ""
}

log_step() {
    log "${MAGENTA}▶${NC}  ${BOLD}$1${NC}"
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

show_help() {
    grep "^#" "$0" | grep -v "^#!/" | sed 's/^# //' | sed 's/^#//'
}

check_prerequisites() {
    log_step "Checking prerequisites..."

    local missing_tools=()

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        missing_tools+=("aws-cli")
    fi

    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        missing_tools+=("python3")
    fi

    # Check jq
    if ! command -v jq &> /dev/null; then
        log_warning "jq not found (optional but recommended)"
    fi

    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_error "Please install missing tools and try again"
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured or invalid"
        log_error "Please configure AWS credentials and try again"
        exit 1
    fi

    log_success "All prerequisites met"
}

get_current_account() {
    aws sts get-caller-identity --query Account --output text 2>/dev/null || echo ""
}

get_current_region() {
    aws configure get region 2>/dev/null || echo "us-east-1"
}

confirm_action() {
    if [ "$FORCE" = true ]; then
        return 0
    fi

    echo -ne "${YELLOW}$1 (y/N): ${NC}"
    read -r response
    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

create_backup() {
    local file="$1"

    if [ -f "$file" ]; then
        local backup_file="$BACKUP_DIR/$(basename "$file")"
        mkdir -p "$BACKUP_DIR"
        cp "$file" "$backup_file"
        log_info "Backed up: $(basename "$file")"
    fi
}

# ============================================================================
# ACCOUNT DETECTION
# ============================================================================

detect_accounts() {
    log_step "Detecting AWS account information..."

    CURRENT_ACCOUNT=$(get_current_account)
    CURRENT_REGION=$(get_current_region)

    if [ -z "$CURRENT_ACCOUNT" ]; then
        log_error "Unable to detect current AWS account"
        exit 1
    fi

    log_info "Current Account: ${BOLD}${CURRENT_ACCOUNT}${NC}"
    log_info "Current Region:  ${BOLD}${CURRENT_REGION}${NC}"
    log_info "Environment:     ${BOLD}${ENV}${NC}"
    log ""

    # Detect old account references
    log_step "Scanning for hardcoded account references..."

    OLD_ACCOUNTS=()

    # Check .deployment-bucket file
    if [ -f "$PROJECT_ROOT/.deployment-bucket" ]; then
        local bucket_account=$(grep -oE '[0-9]{12}' "$PROJECT_ROOT/.deployment-bucket" | head -1)
        if [ -n "$bucket_account" ] && [ "$bucket_account" != "$CURRENT_ACCOUNT" ]; then
            OLD_ACCOUNTS+=("$bucket_account")
            log_warning "Found old account reference in .deployment-bucket: $bucket_account"
        fi
    fi

    # Check scripts for hardcoded accounts
    local hardcoded=$(grep -r -o -E '[0-9]{12}' "$PROJECT_ROOT/glue-etl/" 2>/dev/null | grep -v '.git' | cut -d: -f2 | sort -u)
    for account in $hardcoded; do
        if [ "$account" != "$CURRENT_ACCOUNT" ]; then
            if [[ ! " ${OLD_ACCOUNTS[@]} " =~ " ${account} " ]]; then
                OLD_ACCOUNTS+=("$account")
                log_warning "Found hardcoded account reference: $account"
            fi
        fi
    done

    if [ ${#OLD_ACCOUNTS[@]} -eq 0 ]; then
        log_success "No old account references found"
    else
        log_warning "Found ${#OLD_ACCOUNTS[@]} old account reference(s)"
        for old_account in "${OLD_ACCOUNTS[@]}"; do
            log_info "  → $old_account"
        done
    fi

    log ""
}

# ============================================================================
# FIX HARDCODED REFERENCES
# ============================================================================

fix_deployment_bucket_file() {
    log_step "Fixing .deployment-bucket file..."

    local file="$PROJECT_ROOT/.deployment-bucket"
    local new_bucket="noaa-deployment-${CURRENT_ACCOUNT}-${ENV}"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would update to: $new_bucket"
        return 0
    fi

    create_backup "$file"

    echo "$new_bucket" > "$file"
    log_success "Updated .deployment-bucket: $new_bucket"

    ((COMPLETED_FIXES++))
}

fix_glue_etl_script() {
    log_step "Fixing hardcoded account in Glue ETL script..."

    local file="$PROJECT_ROOT/glue-etl/run-etl-now.sh"

    if [ ! -f "$file" ]; then
        log_warning "File not found: $file (skipping)"
        return 0
    fi

    # Check if file has hardcoded account
    if ! grep -q '[0-9]\{12\}' "$file"; then
        log_info "No hardcoded accounts found in $file"
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would fix account references in run-etl-now.sh"
        return 0
    fi

    create_backup "$file"

    # Replace hardcoded account with variable
    sed -i.bak 's|s3://noaa-athena-results-[0-9]\{12\}-|s3://noaa-athena-results-${ACCOUNT_ID:-'${CURRENT_ACCOUNT}'}-|g' "$file"
    rm -f "$file.bak"

    log_success "Fixed account references in run-etl-now.sh"

    ((COMPLETED_FIXES++))
}

fix_documentation() {
    log_step "Updating documentation with current account..."

    local docs=(
        "$PROJECT_ROOT/OPERATIONAL_STATUS_REPORT.md"
        "$PROJECT_ROOT/COMPREHENSIVE_DIAGNOSTIC_REPORT.md"
    )

    for doc in "${docs[@]}"; do
        if [ -f "$doc" ]; then
            if [ "$DRY_RUN" = true ]; then
                log_info "[DRY RUN] Would update $(basename "$doc")"
            else
                create_backup "$doc"

                # Add note at top of document
                local temp_file="${doc}.tmp"
                echo "> **Note:** This document has been updated for account ${CURRENT_ACCOUNT} on ${TIMESTAMP}" > "$temp_file"
                echo "" >> "$temp_file"
                cat "$doc" >> "$temp_file"
                mv "$temp_file" "$doc"

                log_success "Updated $(basename "$doc")"
                ((COMPLETED_FIXES++))
            fi
        fi
    done
}

apply_all_fixes() {
    log_header "APPLYING FIXES"

    TOTAL_FIXES=3

    fix_deployment_bucket_file
    fix_glue_etl_script
    fix_documentation

    log ""
    log_success "Completed ${COMPLETED_FIXES}/${TOTAL_FIXES} fixes"

    if [ "$DRY_RUN" = true ]; then
        log_info "This was a dry run. No changes were made."
        log_info "Run without --dry-run to apply changes."
    fi
}

# ============================================================================
# DEPLOYMENT
# ============================================================================

deploy_infrastructure() {
    log_header "DEPLOYING INFRASTRUCTURE"

    if [ "$SKIP_DEPLOY" = true ]; then
        log_info "Skipping deployment (--skip-deploy flag)"
        return 0
    fi

    log_step "Starting infrastructure deployment..."

    # Check if deploy script exists
    local deploy_script="$PROJECT_ROOT/scripts/deploy_to_aws.sh"

    if [ ! -f "$deploy_script" ]; then
        log_error "Deploy script not found: $deploy_script"
        return 1
    fi

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would execute: $deploy_script --env $ENV --region $REGION"
        return 0
    fi

    # Run deployment
    log_info "Executing deployment script..."
    log_info "This may take 10-15 minutes..."
    log ""

    cd "$PROJECT_ROOT"

    if bash "$deploy_script" --env "$ENV" --region "$REGION"; then
        log ""
        log_success "Deployment completed successfully"
        return 0
    else
        log ""
        log_error "Deployment failed"
        log_error "Check logs at: $LOG_FILE"
        return 1
    fi
}

# ============================================================================
# VERIFICATION
# ============================================================================

verify_deployment() {
    log_header "VERIFYING DEPLOYMENT"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would verify deployment"
        return 0
    fi

    local checks_passed=0
    local checks_total=6

    # Check 1: S3 Buckets
    log_step "Checking S3 buckets..."
    local data_lake_bucket="noaa-federated-lake-${CURRENT_ACCOUNT}-${ENV}"
    if aws s3 ls "s3://${data_lake_bucket}" &> /dev/null; then
        log_success "Data lake bucket exists: $data_lake_bucket"
        ((checks_passed++))
    else
        log_error "Data lake bucket not found: $data_lake_bucket"
    fi

    # Check 2: Lambda Functions
    log_step "Checking Lambda functions..."
    local lambda_count=$(aws lambda list-functions --query 'Functions[?contains(FunctionName, `noaa-ingest`)].FunctionName' --output text | wc -w)
    if [ "$lambda_count" -gt 0 ]; then
        log_success "Found $lambda_count Lambda function(s)"
        ((checks_passed++))
    else
        log_warning "No Lambda functions found"
    fi

    # Check 3: EventBridge Rules
    log_step "Checking EventBridge rules..."
    local rule_count=$(aws events list-rules --query 'Rules[?contains(Name, `noaa-ingest`)].Name' --output text | wc -w)
    if [ "$rule_count" -gt 0 ]; then
        log_success "Found $rule_count EventBridge rule(s)"
        ((checks_passed++))
    else
        log_warning "No EventBridge rules found"
    fi

    # Check 4: Athena Database
    log_step "Checking Athena databases..."
    local db_count=$(aws athena list-databases --catalog-name AwsDataCatalog --query 'DatabaseList[?contains(Name, `noaa`)].Name' --output text | wc -w)
    if [ "$db_count" -gt 0 ]; then
        log_success "Found $db_count Athena database(s)"
        ((checks_passed++))
    else
        log_warning "No Athena databases found"
    fi

    # Check 5: IAM Roles
    log_step "Checking IAM roles..."
    local role_count=$(aws iam list-roles --query 'Roles[?contains(RoleName, `noaa`)].RoleName' --output text | wc -w)
    if [ "$role_count" -gt 0 ]; then
        log_success "Found $role_count IAM role(s)"
        ((checks_passed++))
    else
        log_warning "No IAM roles found"
    fi

    # Check 6: Recent Data
    log_step "Checking for recent data..."
    if aws s3 ls "s3://${data_lake_bucket}/bronze/" &> /dev/null; then
        log_success "Bronze layer accessible"
        ((checks_passed++))
    else
        log_warning "Bronze layer not accessible yet"
    fi

    log ""
    log_info "Verification complete: ${checks_passed}/${checks_total} checks passed"

    if [ "$checks_passed" -ge 4 ]; then
        log_success "System appears to be operational"
        return 0
    else
        log_warning "System may need additional configuration"
        return 1
    fi
}

# ============================================================================
# SUMMARY REPORT
# ============================================================================

generate_summary() {
    log_header "MIGRATION SUMMARY"

    log_info "Migration Date:      $(date)"
    log_info "Target Account:      ${BOLD}${CURRENT_ACCOUNT}${NC}"
    log_info "Region:              ${BOLD}${REGION}${NC}"
    log_info "Environment:         ${BOLD}${ENV}${NC}"
    log ""

    if [ "$DRY_RUN" = false ]; then
        log_info "Fixes Applied:       ${COMPLETED_FIXES}/${TOTAL_FIXES}"
        log_info "Backup Location:     $BACKUP_DIR"
        log_info "Log File:            $LOG_FILE"
        log ""

        log_step "Next Steps:"
        log_info "1. Verify Lambda functions are running:"
        log_info "   ${CYAN}aws lambda list-functions --query 'Functions[?contains(FunctionName, \`noaa\`)].FunctionName'${NC}"
        log ""
        log_info "2. Check recent data ingestion:"
        log_info "   ${CYAN}aws s3 ls s3://noaa-federated-lake-${CURRENT_ACCOUNT}-${ENV}/bronze/atmospheric/ --recursive | tail${NC}"
        log ""
        log_info "3. Monitor Lambda logs:"
        log_info "   ${CYAN}aws logs tail /aws/lambda/noaa-ingest-atmospheric-${ENV} --follow${NC}"
        log ""
        log_info "4. Test Athena queries:"
        log_info "   ${CYAN}./scripts/validate_endpoints_and_queries.py${NC}"
        log ""
    else
        log_info "This was a DRY RUN - no changes were made"
        log_info "Run without --dry-run to perform actual migration"
        log ""
    fi

    log_success "Migration script completed"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --env)
                ENV="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
                shift 2
                ;;
            --skip-deploy)
                SKIP_DEPLOY=true
                shift
                ;;
            --deploy-only)
                DEPLOY_ONLY=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                log_info "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    # Setup
    mkdir -p "$LOG_DIR"

    # Header
    log_header "NOAA FEDERATED DATA LAKE - ACCOUNT MIGRATION"

    log_info "Migration script started at $(date)"
    log_info "Log file: $LOG_FILE"
    log ""

    # Prerequisites check
    check_prerequisites

    # Detect accounts
    detect_accounts

    # Confirmation
    if [ "$DRY_RUN" = false ] && [ "$FORCE" = false ]; then
        log ""
        log_warning "This script will:"
        log_warning "  • Update configuration files"
        log_warning "  • Fix hardcoded account references"
        if [ "$SKIP_DEPLOY" = false ]; then
            log_warning "  • Deploy infrastructure to account: $CURRENT_ACCOUNT"
        fi
        log_warning "  • Create backups in: $BACKUP_DIR"
        log ""

        if ! confirm_action "Continue with migration?"; then
            log_info "Migration cancelled by user"
            exit 0
        fi
        log ""
    fi

    # Apply fixes
    if [ "$DEPLOY_ONLY" = false ]; then
        apply_all_fixes
    fi

    # Deploy infrastructure
    if [ "$SKIP_DEPLOY" = false ]; then
        deploy_infrastructure
    fi

    # Verify deployment
    if [ "$SKIP_DEPLOY" = false ]; then
        verify_deployment
    fi

    # Summary
    generate_summary

    log ""
    log_success "${BOLD}Migration script completed successfully!${NC}"
    log ""
}

# Run main function
main "$@"
