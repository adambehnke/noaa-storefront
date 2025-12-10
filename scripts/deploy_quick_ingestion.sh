#!/usr/bin/env bash
# Quick deployment of oceanic and atmospheric ingestion

set -e

AWS_PROFILE=noaa-target
AWS_REGION=us-east-1
ENV=dev
ACCOUNT_ID=$(AWS_PROFILE=$AWS_PROFILE aws sts get-caller-identity --query Account --output text)

BUCKET_NAME="noaa-federated-lake-${ACCOUNT_ID}-${ENV}"
LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/noaa-etl-role-${ENV}"

echo "=== Deploying Oceanic Ingestion ==="

cd ingestion/lambdas/oceanic
rm -f lambda_package.zip
zip -rq lambda_package.zip . -x "*.pyc" "__pycache__/*"

LAMBDA_NAME="noaa-ingest-oceanic-${ENV}"

if AWS_PROFILE=$AWS_PROFILE aws lambda get-function --function-name "$LAMBDA_NAME" --region $AWS_REGION > /dev/null 2>&1; then
    echo "Updating $LAMBDA_NAME..."
    AWS_PROFILE=$AWS_PROFILE aws lambda update-function-code \
        --function-name "$LAMBDA_NAME" \
        --zip-file fileb://lambda_package.zip \
        --region $AWS_REGION > /dev/null
else
    echo "Creating $LAMBDA_NAME..."
    AWS_PROFILE=$AWS_PROFILE aws lambda create-function \
        --function-name "$LAMBDA_NAME" \
        --runtime python3.12 \
        --handler lambda_function.lambda_handler \
        --role "$LAMBDA_ROLE_ARN" \
        --zip-file fileb://lambda_package.zip \
        --timeout 300 \
        --memory-size 512 \
        --environment "Variables={ENV=$ENV,BUCKET_NAME=$BUCKET_NAME}" \
        --region $AWS_REGION > /dev/null
fi

cd ../../..

echo "=== Setting up EventBridge Schedule ==="
RULE_NAME="noaa-ingest-oceanic-schedule-${ENV}"

AWS_PROFILE=$AWS_PROFILE aws events put-rule \
    --name "$RULE_NAME" \
    --schedule-expression "rate(5 minutes)" \
    --state ENABLED \
    --region $AWS_REGION > /dev/null

LAMBDA_ARN=$(AWS_PROFILE=$AWS_PROFILE aws lambda get-function --function-name "$LAMBDA_NAME" --region $AWS_REGION --query 'Configuration.FunctionArn' --output text)

AWS_PROFILE=$AWS_PROFILE aws events put-targets \
    --rule "$RULE_NAME" \
    --targets "Id=1,Arn=${LAMBDA_ARN},Input='{\"mode\":\"incremental\",\"hours_back\":1}'" \
    --region $AWS_REGION > /dev/null

AWS_PROFILE=$AWS_PROFILE aws lambda add-permission \
    --function-name "$LAMBDA_NAME" \
    --statement-id "AllowEventBridge-${RULE_NAME}" \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:${AWS_REGION}:${ACCOUNT_ID}:rule/${RULE_NAME}" \
    --region $AWS_REGION > /dev/null 2>&1 || true

echo "=== Triggering Initial Ingestion (24 hours of data) ==="
AWS_PROFILE=$AWS_PROFILE aws lambda invoke \
    --function-name "$LAMBDA_NAME" \
    --invocation-type Event \
    --payload '{"mode":"incremental","hours_back":24}' \
    --region $AWS_REGION \
    /tmp/lambda-response.json > /dev/null

echo ""
echo "✅ Oceanic ingestion deployed and triggered!"
echo "   • Schedule: every 5 minutes"
echo "   • Initial data: last 24 hours"
echo ""
echo "Monitor logs:"
echo "  AWS_PROFILE=$AWS_PROFILE aws logs tail /aws/lambda/$LAMBDA_NAME --follow"
echo ""
echo "Check S3 data:"
echo "  AWS_PROFILE=$AWS_PROFILE aws s3 ls s3://$BUCKET_NAME/bronze/oceanic/ --recursive | head -20"
