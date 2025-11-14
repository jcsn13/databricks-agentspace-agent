# Static External IP Addresses for NAT
resource "google_compute_address" "static_ips" {
  count       = var.static_ip_count
  name        = "databricks-nat-ip-${count.index + 1}"
  region      = var.region
  description = "Static IP ${count.index + 1} for Databricks Agent NAT gateway"

  # Ensure IP addresses are created before NAT configuration
  lifecycle {
    create_before_destroy = true
  }
}

# Cloud Router for NAT control plane
resource "google_compute_router" "router" {
  name        = var.cloud_router_name
  region      = var.region
  network     = google_compute_network.vpc.id
  description = "Cloud Router for Databricks Agent NAT gateway"

  bgp {
    asn = 64514
  }
}

# Cloud NAT Gateway with manual IP allocation
resource "google_compute_router_nat" "nat" {
  name   = var.cloud_nat_gateway_name
  router = google_compute_router.router.name
  region = var.region

  # Use manual IP allocation for predictable static IPs
  nat_ip_allocate_option = "MANUAL_ONLY"
  nat_ips                = google_compute_address.static_ips.*.self_link

  # Configure which subnets to NAT
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"
  subnetwork {
    name                    = google_compute_subnetwork.subnet.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  # Port allocation configuration
  min_ports_per_vm                    = 64
  enable_endpoint_independent_mapping = false
  enable_dynamic_port_allocation      = false

  # Logging configuration for monitoring
  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }

  # Depends on the static IPs being available
  depends_on = [google_compute_address.static_ips]
}
