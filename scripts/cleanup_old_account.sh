#!/bin/bash
###############################################################################
# NOAA Federated Data Lake - Old Account Cleanup Script
#
# This script removes all NOAA-related resources from the OLD account
# (899626030376) after migration to the new account (899626030376).
#
# Usage:
#   ./cleanup_old_account.sh [OPTIONS]
#
# Options:
#   --dry-run              Show what would be deleted without deleting
#   --force                Skip confirmation prompts
#   --keep-data            Keep S3 data, only delete compute resources
#   --backup               Create backup of S3 data before deletion
#   --help                 Show this help message
#
# Safety Features:
#   - Requires explicit confirmation
#   - Dry-run mode by default
#   - Verifies correct account before deletion
#   - Creates backups of critical data
#   - Logs all deletions
#
# DANGER: This script will DELETE resources. Use with caution!
#
###############################################################################

set -e
set -o pipefail

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
readonly NC='\033[0m'

# ============================================================================
# CONFIGURATION
# ============================================================================

# OLD account to clean up
readonly OLD_ACCOUNT="899626030376"
readonly OLD_PROFILE="${OLD_PROFILE:-noaa}"

# NEW account (verification only)
readonly NEW_ACCOUNT="899626030376"

# Script configuration
DRY_RUN=true  # Safe default
FORCE=false
KEEP_DATA=false
BACKUP=false
ENV="dev"

# Paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
BACKUP_DIR="$PROJECT_ROOT/backups/cleanup_$(date +%Y%m%d_%H%M%S)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/cleanup_${TIMESTAMP}.log"

# Counters
TOTAL_RESOURCES=0
DELETED_RESOURCES=0
FAILED_DELETIONS=0

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

log_danger() {
    log "${RED}${BOLD}🔥 DANGER${NC}  $1"
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

confirm_action() {
    if [ "$FORCE" = true ]; then
        return 0
    fi

    echo -ne "${YELLOW}$1 (yes/NO): ${NC}"
    read -r response
    case "$response" in
        yes|YES)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

verify_old_account() {
    log_step "Verifying OLD account connection..."

    local current_account=$(AWS_PROFILE="$OLD_PROFILE" aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")

    if [ -z "$current_account" ]; then
        log_error "Cannot connect to account with profile: $OLD_PROFILE"
        exit 1
    fi

    if [ "$current_account" != "$OLD_ACCOUNT" ]; then
        log_error "Profile $OLD_PROFILE is connected to account $current_account"
        log_error "Expected account: $OLD_ACCOUNT"
        exit 1
    fi

    log_success "Connected to OLD account: $OLD_ACCOUNT"
}

# ============================================================================
# RESOURCE LISTING FUNCTIONS
# ============================================================================

list_lambda_functions() {
    log_step "Scanning Lambda functions..."

    local functions=$(AWS_PROFILE="$OLD_PROFILE" aws lambda list-functions \
        --query 'Functions[?contains(FunctionName, `noaa`)].FunctionName' \
        --output text 2>/dev/null || echo "")

    if [ -z "$functions" ]; then
        log_info "No Lambda functions found"
        return 0
    fi

    local count=$(echo "$functions" | wc -w)
    log_warning "Found $count Lambda function(s):"
    for func in $functions; do
        log "  - $func"
    done

    ((TOTAL_RESOURCES += count))
}

list_eventbridge_rules() {
    log_step "Scanning EventBridge rules..."

    local rules=$(AWS_PROFILE="$OLD_PROFILE" aws events list-rules \
        --query 'Rules[?contains(Name, `noaa`)].Name' \
        --output text 2>/dev/null || echo "")

    if [ -z "$rules" ]; then
        log_info "No EventBridge rules found"
        return 0
    fi

    local count=$(echo "$rules" | wc -w)
    log_warning "Found $count EventBridge rule(s):"
    for rule in $rules; do
        log "  - $rule"
    done

    ((TOTAL_RESOURCES += count))
}

list_s3_buckets() {
    log_step "Scanning S3 buckets..."

    local buckets=$(AWS_PROFILE="$OLD_PROFILE" aws s3 ls \
        | grep noaa \
        | awk '{print $3}' || echo "")

    if [ -z "$buckets" ]; then
        log_info "No S3 buckets found"
        return 0
    fi

    local count=$(echo "$buckets" | wc -l)
    log_warning "Found $count S3 bucket(s):"

    for bucket in $buckets; do
        local size=$(AWS_PROFILE="$OLD_PROFILE" aws s3 ls "s3://$bucket" --recursive --summarize 2>/dev/null | grep "Total Size" | awk '{print $3}' || echo "0")
        local size_gb=$(echo "scale=2; $size / 1073741824" | bc 2>/dev/null || echo "0")
        log "  - $bucket (${size_gb} GB)"
    done

    ((TOTAL_RESOURCES += count))
}

list_athena_databases() {
    log_step "Scanning Athena databases..."

    local databases=$(AWS_PROFILE="$OLD_PROFILE" aws athena list-databases \
        --catalog-name AwsDataCatalog \
        --query 'DatabaseList[?contains(Name, `noaa`)].Name' \
        --output text 2>/dev/null || echo "")

    if [ -z "$databases" ]; then
        log_info "No Athena databases found"
        return 0
    fi

    local count=$(echo "$databases" | wc -w)
    log_warning "Found $count Athena database(s):"
    for db in $databases; do
        log "  - $db"
    done

    ((TOTAL_RESOURCES += count))
}

list_iam_roles() {
    log_step "Scanning IAM roles..."

    local roles=$(AWS_PROFILE="$OLD_PROFILE" aws iam list-roles \
        --query 'Roles[?contains(RoleName, `noaa`)].RoleName' \
        --output text 2>/dev/null || echo "")

    if [ -z "$roles" ]; then
        log_info "No IAM roles found"
        return 0
    fi

    local count=$(echo "$roles" | wc -w)
    log_warning "Found $count IAM role(s):"
    for role in $roles; do
        log "  - $role"
    done

    ((TOTAL_RESOURCES += count))
}

list_cloudformation_stacks() {
    log_step "Scanning CloudFormation stacks..."

    local stacks=$(AWS_PROFILE="$OLD_PROFILE" aws cloudformation list-stacks \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
        --query 'StackSummaries[?contains(StackName, `noaa`)].StackName' \
        --output text 2>/dev/null || echo "")

    if [ -z "$stacks" ]; then
        log_info "No CloudFormation stacks found"
        return 0
    fi

    local count=$(echo "$stacks" | wc -w)
    log_warning "Found $count CloudFormation stack(s):"
    for stack in $stacks; do
        log "  - $stack"
    done

    ((TOTAL_RESOURCES += count))
}

# ============================================================================
# BACKUP FUNCTIONS
# ============================================================================

backup_s3_data() {
    if [ "$BACKUP" != true ]; then
        return 0
    fi

    log_header "BACKING UP S3 DATA"
    log_warning "This may take a while depending on data size..."

    mkdir -p "$BACKUP_DIR"

    local buckets=$(AWS_PROFILE="$OLD_PROFILE" aws s3 ls | grep noaa | awk '{print $3}')

    for bucket in $buckets; do
        log_step "Backing up: $bucket"

        local backup_path="$BACKUP_DIR/$bucket"
        mkdir -p "$backup_path"

        if AWS_PROFILE="$OLD_PROFILE" aws s3 sync "s3://$bucket" "$backup_path" --quiet; then
            log_success "Backed up: $bucket"
        else
            log_error "Failed to backup: $bucket"
        fi
    done

    log_success "Backup completed: $BACKUP_DIR"
}

# ============================================================================
# DELETION FUNCTIONS
# ============================================================================

delete_lambda_functions() {
    log_step "Deleting Lambda functions..."

    local functions=$(AWS_PROFILE="$OLD_PROFILE" aws lambda list-functions \
        --query 'Functions[?contains(FunctionName, `noaa`)].FunctionName' \
        --output text 2>/dev/null || echo "")

    if [ -z "$functions" ]; then
        log_info "No Lambda functions to delete"
        return 0
    fi

    for func in $functions; do
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY RUN] Would delete Lambda: $func"
        else
            if AWS_PROFILE="$OLD_PROFILE" aws lambda delete-function --function-name "$func" 2>/dev/null; then
                log_success "Deleted Lambda: $func"
                ((DELETED_RESOURCES++))
            else
                log_error "Failed to delete Lambda: $func"
                ((FAILED_DELETIONS++))
            fi
        fi
    done
}

delete_eventbridge_rules() {
    log_step "Deleting EventBridge rules..."

    local rules=$(AWS_PROFILE="$OLD_PROFILE" aws events list-rules \
        --query 'Rules[?contains(Name, `noaa`)].Name' \
        --output text 2>/dev/null || echo "")

    if [ -z "$rules" ]; then
        log_info "No EventBridge rules to delete"
        return 0
    fi

    for rule in $rules; do
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY RUN] Would delete EventBridge rule: $rule"
        else
            # Remove targets first
            local targets=$(AWS_PROFILE="$OLD_PROFILE" aws events list-targets-by-rule --rule "$rule" --query 'Targets[].Id' --output text 2>/dev/null || echo "")
            if [ -n "$targets" ]; then
                AWS_PROFILE="$OLD_PROFILE" aws events remove-targets --rule "$rule" --ids $targets 2>/dev/null || true
            fi

            # Delete rule
            if AWS_PROFILE="$OLD_PROFILE" aws events delete-rule --name "$rule" 2>/dev/null; then
                log_success "Deleted EventBridge rule: $rule"
                ((DELETED_RESOURCES++))
            else
                log_error "Failed to delete EventBridge rule: $rule"
                ((FAILED_DELETIONS++))
            fi
        fi
    done
}

delete_s3_buckets() {
    if [ "$KEEP_DATA" = true ]; then
        log_info "Skipping S3 bucket deletion (--keep-data flag)"
        return 0
    fi

    log_step "Deleting S3 buckets..."

    local buckets=$(AWS_PROFILE="$OLD_PROFILE" aws s3 ls | grep noaa | awk '{print $3}')

    if [ -z "$buckets" ]; then
        log_info "No S3 buckets to delete"
        return 0
    fi

    for bucket in $buckets; do
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY RUN] Would delete S3 bucket: $bucket"
        else
            log_warning "Deleting bucket: $bucket (this may take a while)"

            # Empty bucket first
            if AWS_PROFILE="$OLD_PROFILE" aws s3 rm "s3://$bucket" --recursive 2>/dev/null; then
                # Delete bucket
                if AWS_PROFILE="$OLD_PROFILE" aws s3 rb "s3://$bucket" 2>/dev/null; then
                    log_success "Deleted S3 bucket: $bucket"
                    ((DELETED_RESOURCES++))
                else
                    log_error "Failed to delete S3 bucket: $bucket"
                    ((FAILED_DELETIONS++))
                fi
            else
                log_error "Failed to empty S3 bucket: $bucket"
                ((FAILED_DELETIONS++))
            fi
        fi
    done
}

delete_athena_databases() {
    log_step "Deleting Athena databases..."

    local databases=$(AWS_PROFILE="$OLD_PROFILE" aws athena list-databases \
        --catalog-name AwsDataCatalog \
        --query 'DatabaseList[?contains(Name, `noaa`)].Name' \
        --output text 2>/dev/null || echo "")

    if [ -z "$databases" ]; then
        log_info "No Athena databases to delete"
        return 0
    fi

    for db in $databases; do
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY RUN] Would delete Athena database: $db"
        else
            # Note: Athena databases are metadata only, tables reference S3 data
            log_info "Deleting Athena database: $db"

            local query="DROP DATABASE IF EXISTS ${db} CASCADE"
            local query_id=$(AWS_PROFILE="$OLD_PROFILE" aws athena start-query-execution \
                --query-string "$query" \
                --result-configuration "OutputLocation=s3://noaa-athena-results-${OLD_ACCOUNT}-dev/" \
                --query 'QueryExecutionId' \
                --output text 2>/dev/null || echo "")

            if [ -n "$query_id" ]; then
                log_success "Deleted Athena database: $db"
                ((DELETED_RESOURCES++))
            else
                log_error "Failed to delete Athena database: $db"
                ((FAILED_DELETIONS++))
            fi
        fi
    done
}

delete_iam_roles() {
    log_step "Deleting IAM roles..."

    local roles=$(AWS_PROFILE="$OLD_PROFILE" aws iam list-roles \
        --query 'Roles[?contains(RoleName, `noaa`)].RoleName' \
        --output text 2>/dev/null || echo "")

    if [ -z "$roles" ]; then
        log_info "No IAM roles to delete"
        return 0
    fi

    for role in $roles; do
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY RUN] Would delete IAM role: $role"
        else
            # Detach policies first
            local policies=$(AWS_PROFILE="$OLD_PROFILE" aws iam list-attached-role-policies \
                --role-name "$role" \
                --query 'AttachedPolicies[].PolicyArn' \
                --output text 2>/dev/null || echo "")

            for policy in $policies; do
                AWS_PROFILE="$OLD_PROFILE" aws iam detach-role-policy --role-name "$role" --policy-arn "$policy" 2>/dev/null || true
            done

            # Delete inline policies
            local inline_policies=$(AWS_PROFILE="$OLD_PROFILE" aws iam list-role-policies \
                --role-name "$role" \
                --query 'PolicyNames' \
                --output text 2>/dev/null || echo "")

            for policy in $inline_policies; do
                AWS_PROFILE="$OLD_PROFILE" aws iam delete-role-policy --role-name "$role" --policy-name "$policy" 2>/dev/null || true
            done

            # Delete role
            if AWS_PROFILE="$OLD_PROFILE" aws iam delete-role --role-name "$role" 2>/dev/null; then
                log_success "Deleted IAM role: $role"
                ((DELETED_RESOURCES++))
            else
                log_error "Failed to delete IAM role: $role"
                ((FAILED_DELETIONS++))
            fi
        fi
    done
}

delete_cloudformation_stacks() {
    log_step "Deleting CloudFormation stacks..."

    local stacks=$(AWS_PROFILE="$OLD_PROFILE" aws cloudformation list-stacks \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
        --query 'StackSummaries[?contains(StackName, `noaa`)].StackName' \
        --output text 2>/dev/null || echo "")

    if [ -z "$stacks" ]; then
        log_info "No CloudFormation stacks to delete"
        return 0
    fi

    for stack in $stacks; do
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY RUN] Would delete CloudFormation stack: $stack"
        else
            log_warning "Deleting CloudFormation stack: $stack"

            if AWS_PROFILE="$OLD_PROFILE" aws cloudformation delete-stack --stack-name "$stack" 2>/dev/null; then
                log_success "Initiated deletion of stack: $stack"
                ((DELETED_RESOURCES++))
            else
                log_error "Failed to delete stack: $stack"
                ((FAILED_DELETIONS++))
            fi
        fi
    done

    if [ "$DRY_RUN" != true ] && [ -n "$stacks" ]; then
        log_info "Note: CloudFormation stack deletion is asynchronous"
        log_info "Monitor progress with: aws cloudformation describe-stacks --stack-name <stack-name>"
    fi
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --keep-data)
                KEEP_DATA=true
                shift
                ;;
            --backup)
                BACKUP=true
                shift
                ;;
            --no-dry-run)
                DRY_RUN=false
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
    log_header "NOAA FEDERATED DATA LAKE - OLD ACCOUNT CLEANUP"

    log_danger "This script will DELETE resources from account: $OLD_ACCOUNT"
    log_info "Cleanup started at $(date)"
    log_info "Log file: $LOG_FILE"

    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN MODE - No resources will be deleted"
    else
        log_danger "LIVE MODE - Resources WILL BE DELETED"
    fi

    log ""

    # Verify account
    verify_old_account

    # List all resources
    log_header "SCANNING FOR RESOURCES"

    list_lambda_functions
    list_eventbridge_rules
    list_s3_buckets
    list_athena_databases
    list_iam_roles
    list_cloudformation_stacks

    log ""
    log_warning "Total resources found: $TOTAL_RESOURCES"
    log ""

    if [ "$TOTAL_RESOURCES" -eq 0 ]; then
        log_success "No NOAA resources found in account $OLD_ACCOUNT"
        log_success "Account is already clean!"
        exit 0
    fi

    # Confirmation
    if [ "$DRY_RUN" = false ]; then
        log ""
        log_danger "═══════════════════════════════════════════════════════════════"
        log_danger " WARNING: YOU ARE ABOUT TO DELETE $TOTAL_RESOURCES RESOURCES!"
        log_danger " Account: $OLD_ACCOUNT"
        log_danger " This action CANNOT be undone!"
        log_danger "═══════════════════════════════════════════════════════════════"
        log ""

        if [ "$KEEP_DATA" = true ]; then
            log_info "Data will be preserved (--keep-data flag)"
        else
            log_danger "S3 data WILL BE DELETED"
        fi

        log ""

        if ! confirm_action "Type 'yes' to confirm deletion of $TOTAL_RESOURCES resources"; then
            log_info "Cleanup cancelled by user"
            exit 0
        fi

        log ""
        log_warning "Final confirmation: Are you absolutely sure?"
        if ! confirm_action "Type 'yes' again to proceed"; then
            log_info "Cleanup cancelled by user"
            exit 0
        fi

        log ""
    fi

    # Backup data if requested
    if [ "$BACKUP" = true ]; then
        backup_s3_data
    fi

    # Delete resources
    log_header "DELETING RESOURCES"

    delete_lambda_functions
    delete_eventbridge_rules
    delete_cloudformation_stacks
    delete_athena_databases
    delete_iam_roles
    delete_s3_buckets

    # Summary
    log_header "CLEANUP SUMMARY"

    log_info "Cleanup completed at $(date)"
    log_info "Total resources found: $TOTAL_RESOURCES"

    if [ "$DRY_RUN" = true ]; then
        log_info "Dry run completed - no resources were deleted"
        log_info "Run with --no-dry-run to perform actual deletion"
    else
        log_success "Resources deleted: $DELETED_RESOURCES"
        if [ "$FAILED_DELETIONS" -gt 0 ]; then
            log_error "Failed deletions: $FAILED_DELETIONS"
        fi

        if [ "$BACKUP" = true ]; then
            log_info "Backup location: $BACKUP_DIR"
        fi
    fi

    log_info "Log file: $LOG_FILE"
    log ""

    if [ "$DRY_RUN" = false ] && [ "$DELETED_RESOURCES" -gt 0 ]; then
        log_success "Old account cleanup completed successfully!"
    fi
}

# Run main function
main "$@"
