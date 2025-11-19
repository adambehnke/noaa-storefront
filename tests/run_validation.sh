#!/bin/bash
# Quick validation runner with timeout
./scripts/validate_all_endpoints.sh dev 2>&1 | tee -a validation_output.log
echo "Done! Report file: $(ls -t validation_report_*.md | head -1)"
