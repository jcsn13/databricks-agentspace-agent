#!/bin/bash
set -e

# Colors for output formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Fetching static IP addresses for Databricks allowlisting...${NC}"
echo ""

# Check if we're in the terraform directory
if [ ! -f "main.tf" ]; then
    echo -e "${RED}Error: This script must be run from the terraform/ directory${NC}"
    echo "Please run: cd terraform && ./scripts/get_static_ips.sh"
    exit 1
fi

# Check if Terraform is initialized
if [ ! -d ".terraform" ]; then
    echo -e "${YELLOW}Warning: Terraform not initialized. Running terraform init...${NC}"
    terraform init
fi

# Check if infrastructure is deployed
if ! terraform show >/dev/null 2>&1; then
    echo -e "${RED}Error: No Terraform state found. Please deploy the infrastructure first:${NC}"
    echo "  terraform plan"
    echo "  terraform apply"
    exit 1
fi

# Get the static IPs from Terraform output
echo -e "${BLUE}=== Static IP Addresses for Databricks Allowlisting ===${NC}"
STATIC_IPS=$(terraform output -json static_ip_addresses 2>/dev/null | jq -r '.[]' 2>/dev/null)

if [ $? -ne 0 ] || [ -z "$STATIC_IPS" ]; then
    echo -e "${RED}Error: Could not retrieve static IP addresses from Terraform output${NC}"
    echo "Please ensure the infrastructure is deployed and outputs are available."
    exit 1
fi

echo "$STATIC_IPS" | while read -r ip; do
    echo -e "  ${GREEN}✓ $ip${NC}"
done

# Get additional information
echo ""
echo -e "${BLUE}=== Additional Information ===${NC}"
NETWORK_ATTACHMENT=$(terraform output -raw network_attachment_id 2>/dev/null || echo "Not available")
REGION=$(terraform output -raw region 2>/dev/null || echo "Not available")
IP_COUNT=$(echo "$STATIC_IPS" | wc -l)

echo -e "  ${YELLOW}IP Count:${NC} $IP_COUNT"
echo -e "  ${YELLOW}Region:${NC} $REGION"
echo -e "  ${YELLOW}Network Attachment:${NC} $NETWORK_ATTACHMENT"

echo ""
echo -e "${BLUE}=== Databricks Configuration Instructions ===${NC}"
echo "1. Log into your Databricks workspace"
echo "2. Navigate to Admin Console > Settings > IP Access Lists"
echo "3. Create a new IP access list or edit an existing one"
echo "4. Add the above IP addresses (one per line or as a range)"
echo "5. Save the configuration"
echo "6. Wait 5-10 minutes for changes to propagate"
echo ""
echo -e "${GREEN}Note: Your Databricks Agent will use these static IPs for all outbound connections${NC}"

# Optional: Create a CSV file for easy import
CSV_FILE="databricks_static_ips.csv"
echo "ip_address,description" > "$CSV_FILE"
counter=1
echo "$STATIC_IPS" | while read -r ip; do
    echo "$ip,Databricks Agent Static IP $counter" >> "$CSV_FILE"
    counter=$((counter + 1))
done

echo ""
echo -e "${YELLOW}CSV file created: $CSV_FILE${NC}"
echo "You can import this file into Databricks or use it for documentation."
