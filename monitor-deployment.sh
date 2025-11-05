#!/bin/bash
echo "Monitoring CloudFormation deployment..."
echo "This may take 10-15 minutes"
echo ""

while true; do
    STATUS=$(aws cloudformation describe-stacks \
        --stack-name noaa-federated-lake-dev \
        --region us-east-1 \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null)
    
    TIMESTAMP=$(date +"%H:%M:%S")
    
    if [ "$STATUS" == "CREATE_COMPLETE" ]; then
        echo "[$TIMESTAMP] ✓ Stack creation COMPLETE!"
        exit 0
    elif [ "$STATUS" == "CREATE_FAILED" ] || [ "$STATUS" == "ROLLBACK_IN_PROGRESS" ] || [ "$STATUS" == "ROLLBACK_COMPLETE" ]; then
        echo "[$TIMESTAMP] ✗ Stack creation FAILED: $STATUS"
        exit 1
    elif [ "$STATUS" == "CREATE_IN_PROGRESS" ]; then
        # Get latest events
        LATEST=$(aws cloudformation describe-stack-events \
            --stack-name noaa-federated-lake-dev \
            --region us-east-1 \
            --max-items 1 \
            --query 'StackEvents[0].{Resource:LogicalResourceId,Status:ResourceStatus}' \
            --output text 2>/dev/null)
        echo "[$TIMESTAMP] Creating... Latest: $LATEST"
    else
        echo "[$TIMESTAMP] Status: $STATUS"
    fi
    
    sleep 30
done
