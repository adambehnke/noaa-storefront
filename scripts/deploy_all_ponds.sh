#!/bin/bash
# Deploy all data pond ingestions

set -e
AWS_PROFILE=noaa-target
REGION=us-east-1
ENV=dev
ACCOUNT_ID=899626030376
BUCKET="noaa-federated-lake-${ACCOUNT_ID}-${ENV}"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/noaa-etl-role-${ENV}"

PONDS=("atmospheric" "buoy" "climate" "spatial" "terrestrial")
SCHEDULES=("rate(5 minutes)" "rate(5 minutes)" "rate(1 hour)" "rate(1 day)" "rate(30 minutes)")

echo "=== Deploying All Data Pond Ingestions ==="

for i in "${!PONDS[@]}"; do
  pond="${PONDS[$i]}"
  schedule="${SCHEDULES[$i]}"
  
  echo ""
  echo "[$((i+1))/${#PONDS[@]}] Deploying ${pond}..."
  
  cd "ingestion/lambdas/${pond}"
  rm -f lambda_package.zip
  zip -rq lambda_package.zip . -x "*.pyc" "__pycache__/*" "*.git/*"
  
  LAMBDA_NAME="noaa-ingest-${pond}-${ENV}"
  
  if AWS_PROFILE=$AWS_PROFILE aws lambda get-function --function-name "$LAMBDA_NAME" --region $REGION > /dev/null 2>&1; then
    echo "  Updating Lambda..."
    AWS_PROFILE=$AWS_PROFILE aws lambda update-function-code \
      --function-name "$LAMBDA_NAME" \
      --zip-file fileb://lambda_package.zip \
      --region $REGION > /dev/null
  else
    echo "  Creating Lambda..."
    AWS_PROFILE=$AWS_PROFILE aws lambda create-function \
      --function-name "$LAMBDA_NAME" \
      --runtime python3.12 \
      --handler lambda_function.lambda_handler \
      --role "$ROLE_ARN" \
      --zip-file fileb://lambda_package.zip \
      --timeout 300 \
      --memory-size 512 \
      --environment "Variables={ENV=$ENV,BUCKET_NAME=$BUCKET}" \
      --region $REGION > /dev/null
  fi
  
  cd ../../..
  
  # Setup schedule
  RULE_NAME="noaa-ingest-${pond}-schedule-${ENV}"
  echo "  Creating schedule: ${schedule}"
  
  AWS_PROFILE=$AWS_PROFILE aws events put-rule \
    --name "$RULE_NAME" \
    --schedule-expression "$schedule" \
    --state ENABLED \
    --region $REGION > /dev/null
  
  LAMBDA_ARN=$(AWS_PROFILE=$AWS_PROFILE aws lambda get-function \
    --function-name "$LAMBDA_NAME" \
    --region $REGION \
    --query 'Configuration.FunctionArn' \
    --output text)
  
  AWS_PROFILE=$AWS_PROFILE aws events put-targets \
    --rule "$RULE_NAME" \
    --targets "Id=1,Arn=${LAMBDA_ARN},Input='{\"mode\":\"incremental\",\"hours_back\":1}'" \
    --region $REGION > /dev/null
  
  AWS_PROFILE=$AWS_PROFILE aws lambda add-permission \
    --function-name "$LAMBDA_NAME" \
    --statement-id "AllowEventBridge-${RULE_NAME}" \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/${RULE_NAME}" \
    --region $REGION > /dev/null 2>&1 || true
  
  # Trigger initial ingestion
  echo "  Triggering initial ingestion..."
  echo '{"mode":"incremental","hours_back":48}' | \
    AWS_PROFILE=$AWS_PROFILE aws lambda invoke \
    --function-name "$LAMBDA_NAME" \
    --cli-binary-format raw-in-base64-out \
    --payload file:///dev/stdin \
    --invocation-type Event \
    /tmp/lambda-${pond}.json --region $REGION > /dev/null 2>&1 || true
  
  echo "  ✓ ${pond} deployed"
done

echo ""
echo "=== All Ponds Deployed! ==="
echo ""
echo "Active Ingestions:"
AWS_PROFILE=$AWS_PROFILE aws events list-rules \
  --name-prefix "noaa-ingest" \
  --query 'Rules[*].[Name,State,ScheduleExpression]' \
  --output table --region $REGION
