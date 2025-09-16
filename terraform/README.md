# Terraform Static IP Configuration for Vertex AI Agent Engine

This Terraform configuration creates the necessary Google Cloud infrastructure to provide static external IP addresses for your Vertex AI Agent Engine deployment, enabling IP allowlisting in Databricks through an HTTP proxy architecture.

## 🎯 Overview

The Databricks workspace has IP restrictions requiring allowlisting of specific IP addresses. This Terraform configuration solves this by:

1. **Creating VPC Infrastructure**: Custom VPC network and subnet for the agent
2. **Setting up HTTP Proxy**: Squid proxy to force all traffic through NAT gateway
3. **Setting up Cloud NAT**: Manual IP allocation with 4 static external IP addresses
4. **Private Service Connect**: Network attachment for Agent Engine connectivity
5. **Automated Deployment**: Integration with existing Python deployment scripts

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Google Cloud Project                            │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌────────────────────────────────────────────┐   │
│  │   Vertex AI     │    │              VPC Network                  │   │
│  │  Agent Engine   │◄───┤      databricks-agent-vpc (10.0.0.0/24)   │   │
│  │   (via PSC)     │    │                                           │   │
│  └─────────────────┘    │  ┌──────────────┐  ┌──────────────────────┐│   │
│                         │  │ HTTP Proxy   │  │    Cloud Router     ││   │
│  ┌─────────────────┐    │  │ (Squid:3128) │  │                     ││   │
│  │ Static IP Pool  │    │  │ 10.0.0.x     │  └──────────────────────┘│   │
│  │ • IP-1: x.x.x.x │◄───┤  └──────────────┘                        │   │
│  │ • IP-2: x.x.x.x │    │           │                               │   │
│  │ • IP-3: x.x.x.x │    │           ▼                               │   │
│  │ • IP-4: x.x.x.x │    │  ┌─────────────────────────────────────────┐│   │
│  └─────────────────┘    │  │            Cloud NAT                   ││   │
│                         │  │      (Manual IP Allocation)            ││   │
│                         │  └─────────────────────────────────────────┘│   │
│                         └────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │   Databricks    │
                            │   (Accessible   │
                            │  via Static IPs)│
                            └─────────────────┘
```

**Traffic Flow**: Agent Engine → PSC Interface → VPC Subnet → HTTP Proxy (port 3128) → NAT Gateway → Static IPs → Internet

## ⚠️ Important Security Note

> **Service Principal OAuth Tokens Bypass IP Access Lists**
> 
> Databricks Service Principal OAuth authentication (M2M) **intentionally bypasses IP access list restrictions**. This is by design and applies to:
> - Service Principal OAuth tokens
> - Machine-to-machine authentication
> 
> However, your traffic **still uses the static IPs** - it's just that Databricks doesn't enforce IP restrictions on OAuth tokens. This is standard Databricks behavior and not a configuration issue.

## 📋 Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Required APIs** enabled:
   - Compute Engine API
   - Vertex AI API  
   - Service Networking API
3. **IAM Permissions**:
   - `roles/compute.networkAdmin`
   - `roles/aiplatform.user`
   - `roles/serviceusage.serviceUsageAdmin`
4. **Tools Installed**:
   - [Terraform](https://terraform.io) >= 1.0
   - [Google Cloud CLI](https://cloud.google.com/sdk)
   - `jq` (for the IP display script)

## 🚀 Quick Start

### 1. Clone and Configure

```bash
# Navigate to the terraform directory
cd terraform/

# Copy the example configuration
cp terraform.tfvars.example terraform.tfvars

# Edit with your project details
vim terraform.tfvars
```

### 2. Required Configuration

Edit `terraform.tfvars`:

```hcl
# Required
project_id = "your-gcp-project-id"
region     = "us-central1"

# Optional (defaults provided)
vpc_network_name        = "databricks-agent-vpc"
static_ip_count         = 4
deploy_agent           = true
```

### 3. Initialize and Deploy

```bash
# Initialize Terraform (first time only)
terraform init

# Review the planned changes
terraform plan

# Apply the configuration
terraform apply
```

### 4. Get Static IP Addresses

```bash
# Run the utility script to get IPs for Databricks
./scripts/get_static_ips.sh

# Or get proxy configuration
terraform output proxy_configuration
```

## 📁 File Structure

```
terraform/
├── main.tf                 # Main infrastructure configuration
├── variables.tf            # Input variable definitions
├── outputs.tf              # Output definitions
├── proxy.tf                # HTTP proxy (Squid) configuration
├── nat.tf                  # NAT gateway and static IP configuration
├── network_attachment.tf   # Private Service Connect setup
├── firewall.tf             # VPC firewall rules
├── agent_deployment.tf     # Agent deployment integration
├── backend.tf              # Terraform state backend configuration
├── terraform.tfvars.example # Configuration template
├── scripts/
│   └── get_static_ips.sh   # Utility to display static IPs
└── README.md               # This file
```

## 🔧 Configuration Options

### Core Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `project_id` | GCP Project ID | - | ✅ |
| `region` | GCP Region | `us-central1` | ❌ |
| `static_ip_count` | Number of static IPs | `4` | ❌ |
| `deploy_agent` | Auto-deploy agent | `true` | ❌ |

### Network Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `vpc_network_name` | VPC network name | `databricks-agent-vpc` |
| `vpc_subnet_name` | Subnet name | `databricks-agent-subnet` |
| `vpc_subnet_cidr` | Subnet CIDR range | `10.0.0.0/24` |

### NAT Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `cloud_router_name` | Cloud Router name | `databricks-agent-router` |
| `cloud_nat_gateway_name` | NAT gateway name | `databricks-agent-nat` |

## 🌐 Outputs

After deployment, Terraform provides these outputs:

```bash
# Get all outputs
terraform output

# Get specific output
terraform output static_ip_addresses
terraform output network_attachment_id
terraform output proxy_configuration
```

### Available Outputs

- `static_ip_addresses` - List of static IP addresses for allowlisting
- `network_attachment_id` - Network attachment ID for Agent Engine
- `proxy_configuration` - HTTP proxy details (IP, URL, zone)
- `databricks_allowlist_summary` - Complete summary for Databricks configuration

## 🛠️ Operations

### View Static IP Addresses

```bash
# Using the utility script (recommended)
./scripts/get_static_ips.sh

# Using Terraform directly
terraform output -json static_ip_addresses | jq -r '.[]'
```

### Check Proxy Status

```bash
# Get proxy information
terraform output proxy_configuration

# SSH into proxy to check status
gcloud compute ssh databricks-agent-proxy --zone=us-central1-a --command="sudo systemctl status squid"

# View proxy logs
gcloud compute ssh databricks-agent-proxy --zone=us-central1-a --command="sudo tail -f /var/log/squid/access.log"
```

### Update Configuration

```bash
# Modify terraform.tfvars or .tf files
vim terraform.tfvars

# Review changes
terraform plan

# Apply updates
terraform apply
```

### Scale IP Addresses

To change the number of static IPs:

```hcl
# In terraform.tfvars
static_ip_count = 6  # Increase from 4 to 6
```

```bash
terraform apply
```

### Recreate Proxy

If you need to recreate the proxy with updated configuration:

```bash
# Destroy and recreate proxy
terraform destroy -target=google_compute_instance.proxy
terraform apply
```

### Destroy Infrastructure

```bash
# Remove all resources (Warning: This is irreversible!)
terraform destroy
```

## 🔐 Databricks Configuration

After deployment, configure Databricks IP allowlisting:

### Step 1: Get Static IP Addresses

```bash
cd terraform/
./scripts/get_static_ips.sh
```

### Step 2: Configure Databricks

1. **Log into Databricks workspace**
2. **Navigate to**: Admin Console → Settings → IP Access Lists
3. **Create new IP access list** or edit existing
4. **Add the static IP addresses** (one per line)
5. **Save configuration**
6. **Wait 5-10 minutes** for changes to propagate

### Step 3: Test Connectivity

Deploy your agent and test Databricks connectivity to ensure the traffic is flowing through your static IPs.

## 💰 Cost Estimation

**Monthly costs** (us-central1 region):

| Resource | Quantity | Cost/Month |
|----------|----------|------------|
| Cloud NAT Gateway | 1 | ~$45 |
| Static IP Addresses | 4 | ~$6 |
| HTTP Proxy (e2-small) | 1 | ~$14 |
| VPC Network | 1 | Free |
| **Total** | | **~$65** |

*Costs may vary by region and usage patterns.*

## 🔍 Troubleshooting

### Common Issues

#### "Permission Denied" Errors

```bash
# Check current user permissions
gcloud auth list
gcloud projects get-iam-policy $PROJECT_ID

# Re-authenticate if needed
gcloud auth login
gcloud auth application-default login
```

#### "API Not Enabled" Errors

```bash
# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable servicenetworking.googleapis.com
```

#### Proxy Connection Issues

```bash
# Check if Squid is running
gcloud compute ssh databricks-agent-proxy --zone=us-central1-a \
  --command="sudo systemctl status squid"

# Check proxy configuration
gcloud compute ssh databricks-agent-proxy --zone=us-central1-a \
  --command="sudo squid -k parse"

# View proxy setup logs
gcloud compute ssh databricks-agent-proxy --zone=us-central1-a \
  --command="sudo cat /var/log/proxy-setup.log"

# Test proxy connectivity
PROXY_IP=$(terraform output -json proxy_configuration | jq -r '.internal_ip')
curl -x http://$PROXY_IP:3128 https://httpbin.org/ip
```

#### Agent Can't Connect to Proxy

```bash
# Verify proxy IP is correctly set
echo $PROXY_INTERNAL_IP

# Check if agent and proxy are in same subnet
gcloud compute instances list --filter="name:(databricks-agent-proxy OR agent-instance)"

# Verify firewall allows proxy traffic
gcloud compute firewall-rules list --filter="name:*proxy*"
```

#### Terraform State Issues

```bash
# Refresh state if resources were modified outside Terraform
terraform refresh

# Import existing resources if needed
terraform import google_compute_address.static_ips[0] projects/PROJECT/regions/REGION/addresses/IP_NAME
```

#### Agent Deployment Fails

```bash
# Check environment variables
echo $NETWORK_ATTACHMENT_ID
echo $STATIC_IPS
echo $PROXY_INTERNAL_IP

# Verify network attachment exists
gcloud compute network-attachments list --region=us-central1
```

### Debugging Tips

1. **Enable detailed logging**:
   ```bash
   export TF_LOG=DEBUG
   terraform apply
   ```

2. **Check Terraform state**:
   ```bash
   terraform show
   terraform state list
   ```

3. **Validate configuration**:
   ```bash
   terraform validate
   terraform fmt -check
   ```

4. **Test proxy manually**:
   ```bash
   # From inside the VPC (or another VM in same subnet)
   PROXY_IP=$(terraform output -json proxy_configuration | jq -r '.internal_ip')
   curl -v -x http://$PROXY_IP:3128 https://api.ipify.org
   ```

### Proxy-Specific Troubleshooting

#### Squid Configuration Issues

```bash
# Check Squid configuration syntax
gcloud compute ssh databricks-agent-proxy --zone=us-central1-a \
  --command="sudo squid -k parse"

# View Squid cache log
gcloud compute ssh databricks-agent-proxy --zone=us-central1-a \
  --command="sudo tail -f /var/log/squid/cache.log"

# Restart Squid if needed
gcloud compute ssh databricks-agent-proxy --zone=us-central1-a \
  --command="sudo systemctl restart squid"
```

#### Verify Static IP Usage

```bash
# Test that traffic goes through static IPs
PROXY_IP=$(terraform output -json proxy_configuration | jq -r '.internal_ip')
EXTERNAL_IP=$(curl -s -x http://$PROXY_IP:3128 https://httpbin.org/ip | jq -r '.origin')
echo "Traffic is using IP: $EXTERNAL_IP"

# Check if it matches one of your static IPs
terraform output static_ip_addresses | grep $EXTERNAL_IP
```

## 🧹 Cleanup

### Partial Cleanup (Keep Infrastructure)

To disable automatic agent deployment:

```hcl
# In terraform.tfvars
deploy_agent = false
```

### Complete Cleanup

```bash
# Destroy all resources
terraform destroy

# Remove Terraform state (optional)
rm -rf .terraform
rm terraform.tfstate*
```

## 🆘 Support

### Documentation Links

- [Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine)
- [Private Service Connect](https://cloud.google.com/vpc/docs/about-private-service-connect-interfaces)
- [Cloud NAT](https://cloud.google.com/nat/docs)
- [Squid Proxy](http://www.squid-cache.org/Doc/config/)
- [Terraform Google Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)

### Getting Help

1. **Check the logs** in Terraform output
2. **Review** Google Cloud Console for resource status
3. **Validate** your configuration with `terraform plan`
4. **Test proxy connectivity** before deploying agent
5. **Check Squid logs** for connection issues

---

**🎯 Summary**: This Terraform configuration provides a complete solution for static IP assignment to Vertex AI Agent Engine through an HTTP proxy architecture. The Squid proxy ensures all external traffic routes through your NAT gateway and static IPs, enabling secure Databricks connectivity. The infrastructure is production-ready and includes automated deployment integration.

**⚡ Key Benefits**:
- ✅ Guaranteed static IP usage for all external traffic
- ✅ Simple HTTP proxy architecture (no complex DNS manipulation)
- ✅ Easy to debug and monitor
- ✅ Works with Service Principal OAuth (even though IP restrictions don't apply)
- ✅ Automatic deployment integration
