# Infrastructure Outputs

# Static IP Addresses for Databricks allowlisting
output "static_ip_addresses" {
  description = "List of static IP addresses used by the NAT gateway"
  value       = google_compute_address.static_ips.*.address
}

# Network Attachment ID for Agent Engine deployment
output "network_attachment_id" {
  description = "Network attachment ID for Vertex AI Agent Engine Private Service Connect"
  value       = google_compute_network_attachment.psc_attachment.id
}

# VPC Network information
output "vpc_network_name" {
  description = "Name of the VPC network"
  value       = google_compute_network.vpc.name
}

output "vpc_network_id" {
  description = "ID of the VPC network"
  value       = google_compute_network.vpc.id
}

# Subnet information
output "subnet_name" {
  description = "Name of the subnet"
  value       = google_compute_subnetwork.subnet.name
}

output "subnet_id" {
  description = "ID of the subnet"
  value       = google_compute_subnetwork.subnet.id
}

output "subnet_cidr" {
  description = "CIDR range of the subnet"
  value       = google_compute_subnetwork.subnet.ip_cidr_range
}

# NAT Gateway information
output "nat_gateway_name" {
  description = "Name of the Cloud NAT gateway"
  value       = google_compute_router_nat.nat.name
}

output "cloud_router_name" {
  description = "Name of the Cloud Router"
  value       = google_compute_router.router.name
}

# Static IP details (with names)
output "static_ip_details" {
  description = "Detailed information about static IP addresses"
  value = [
    for ip in google_compute_address.static_ips : {
      name    = ip.name
      address = ip.address
      region  = ip.region
    }
  ]
}

# Summary output for easy reference
output "databricks_allowlist_summary" {
  description = "Summary information for Databricks IP allowlisting"
  value = {
    static_ips         = google_compute_address.static_ips.*.address
    ip_count           = length(google_compute_address.static_ips.*.address)
    network_attachment = google_compute_network_attachment.psc_attachment.id
    region             = var.region
  }
}
