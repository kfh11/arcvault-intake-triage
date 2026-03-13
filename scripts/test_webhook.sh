#!/bin/bash
# Test all 5 sample inputs against the n8n webhook
# Usage: ./scripts/test_webhook.sh [base_url]
# Default: http://localhost:5678

BASE_URL="${1:-http://localhost:5678}"
WEBHOOK="$BASE_URL/webhook/arcvault-triage"

echo "Testing ArcVault Intake Triage Pipeline"
echo "Webhook: $WEBHOOK"
echo "========================================"

echo ""
echo "--- Input #1: Bug Report (403 error, single user) ---"
curl -s -X POST "$WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d '{"source":"Email","message":"Hi, I tried logging in this morning and keep getting a 403 error. My account is arcvault.io/user/jsmith. This started after your update last Tuesday."}' | python3 -m json.tool

echo ""
echo "--- Input #2: Feature Request (bulk export) ---"
curl -s -X POST "$WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d '{"source":"Web Form","message":"We'\''d love to see a bulk export feature for our audit logs. We'\''re a compliance-heavy org and this would save us hours every month."}' | python3 -m json.tool

echo ""
echo "--- Input #3: Billing Issue (invoice discrepancy > $500) ---"
curl -s -X POST "$WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d '{"source":"Support Portal","message":"Invoice #8821 shows a charge of $1,240 but our contract rate is $980/month. Can someone look into this?"}' | python3 -m json.tool

echo ""
echo "--- Input #4: Technical Question (SSO with Okta) ---"
curl -s -X POST "$WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d '{"source":"Email","message":"I'\''m not sure if this is the right place to ask, but is there a way to set up SSO with Okta? We'\''re evaluating switching our auth provider."}' | python3 -m json.tool

echo ""
echo "--- Input #5: Incident/Outage (dashboard down, multiple users) ---"
curl -s -X POST "$WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d '{"source":"Web Form","message":"Your dashboard stopped loading for us around 2pm EST. Checked our end — it'\''s definitely on yours. Multiple users affected."}' | python3 -m json.tool

echo ""
echo "========================================"
echo "All 5 inputs tested."
