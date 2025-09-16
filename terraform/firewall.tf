# Firewall Rules for VPC Network

# Allow HTTPS egress traffic for external connectivity
resource "google_compute_firewall" "allow_https_egress" {
  name    = "${var.vpc_network_name}-allow-https-egress"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  direction          = "EGRESS"
  destination_ranges = ["0.0.0.0/0"]
  priority           = 1000

  description = "Allow HTTPS egress for external API calls"
}

# Allow HTTP egress traffic (some APIs might need this)
resource "google_compute_firewall" "allow_http_egress" {
  name    = "${var.vpc_network_name}-allow-http-egress"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }

  direction          = "EGRESS"
  destination_ranges = ["0.0.0.0/0"]
  priority           = 1000

  description = "Allow HTTP egress for external API calls"
}

# Allow all internal communication within the subnet
resource "google_compute_firewall" "allow_internal" {
  name    = "${var.vpc_network_name}-allow-internal"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = [var.vpc_subnet_cidr]
  priority      = 1000

  description = "Allow all internal communication within the subnet"
}

# Allow egress to Google APIs and services (private.googleapis.com)
resource "google_compute_firewall" "allow_google_apis_egress" {
  name    = "${var.vpc_network_name}-allow-google-apis-egress"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  direction          = "EGRESS"
  destination_ranges = ["199.36.153.8/30"] # private.googleapis.com range
  priority           = 900

  description = "Allow egress to Google APIs via private.googleapis.com"
}
