# HTTP Proxy Configuration for forcing external traffic through static IPs
# This proxy ensures Agent Engine traffic routes through our NAT gateway

# Create a Compute Engine instance for the proxy
resource "google_compute_instance" "proxy" {
  name         = "databricks-agent-proxy"
  machine_type = "e2-small" # Small instance is sufficient for proxy
  zone         = "${var.region}-a"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
      type  = "pd-standard"
    }
  }

  network_interface {
    network    = google_compute_network.vpc.id
    subnetwork = google_compute_subnetwork.subnet.id
    # No external IP - all traffic must go through NAT for static IPs
  }

  tags = ["proxy-server"]

  metadata_startup_script = <<-EOT
    #!/bin/bash
    
    # Log function
    log() {
      echo "[$(date)] $1" | tee -a /var/log/proxy-setup.log
    }
    
    log "Starting proxy setup..."
    
    # Update system
    log "Updating package lists..."
    apt-get update
    
    log "Installing Squid..."
    apt-get install -y squid
    
    # Stop squid before configuring
    log "Stopping Squid service..."
    systemctl stop squid || true
    
    # Backup original config if it exists
    if [ -f /etc/squid/squid.conf ]; then
      log "Backing up original Squid config..."
      cp /etc/squid/squid.conf /etc/squid/squid.conf.backup
    fi
    
    # Configure Squid proxy for transparent forwarding
    log "Writing new Squid configuration..."
    cat > /etc/squid/squid.conf <<'EOF'
    # Squid configuration for Databricks Agent proxy
    
    # Listen on all interfaces
    http_port 3128
    
    # Access control lists
    acl localnet src 10.0.0.0/24       # Our VPC subnet (matches terraform.tfvars)
    acl SSL_ports port 443
    acl Safe_ports port 80              # http
    acl Safe_ports port 443             # https
    acl Safe_ports port 21              # ftp
    acl Safe_ports port 1025-65535      # unregistered ports
    acl CONNECT method CONNECT
    
    # Allow Databricks domains (covers all subdomains)
    acl databricks_domains dstdomain .databricks.com .cloud.databricks.com
    
    # Deny unsafe ports
    http_access deny !Safe_ports
    
    # Allow CONNECT for SSL ports from local network
    http_access allow CONNECT SSL_ports localnet
    
    # Allow access to Databricks from local network
    http_access allow databricks_domains localnet
    
    # Allow localhost
    http_access allow localhost manager
    http_access deny manager
    
    # Allow local network
    http_access allow localnet
    http_access allow localhost
    
    # Deny all other access
    http_access deny all
    
    # Forwarding
    forwarded_for on
    via off  # Don't add Via header to avoid detection
    
    # DNS
    dns_nameservers 8.8.8.8 8.8.4.4
    
    # Cache (disabled for transparent proxy)
    cache deny all
    
    # Logging
    access_log /var/log/squid/access.log
    cache_log /var/log/squid/cache.log
    
    # Keep connections alive
    client_persistent_connections on
    server_persistent_connections on
    
    # Timeouts
    connect_timeout 60 seconds
    request_timeout 5 minutes
    
    # Buffer sizes for better performance
    request_header_max_size 64 KB
    request_body_max_size 0
    
    # Core dumps for debugging
    coredump_dir /var/spool/squid
    
    # Refresh patterns (minimal for proxy-only)
    refresh_pattern ^ftp:           1440    20%     10080
    refresh_pattern ^gopher:        1440    0%      1440
    refresh_pattern -i (/cgi-bin/|\?) 0     0%      0
    refresh_pattern .               0       20%     4320
    EOF
    
    # Test configuration
    log "Testing Squid configuration..."
    if squid -k parse 2>&1; then
      log "Configuration is valid"
    else
      log "ERROR: Invalid Squid configuration!"
      squid -k parse 2>&1 | tee -a /var/log/proxy-setup.log
      exit 1
    fi
    
    # Restart Squid with new configuration
    log "Starting Squid service..."
    systemctl restart squid
    
    # Check if Squid started successfully
    sleep 5
    if systemctl is-active --quiet squid; then
      log "SUCCESS: Squid proxy is running!"
      systemctl enable squid
    else
      log "ERROR: Squid failed to start!"
      systemctl status squid | tee -a /var/log/proxy-setup.log
      journalctl -xeu squid.service | tail -50 | tee -a /var/log/proxy-setup.log
      exit 1
    fi
    
    # Enable IP forwarding
    log "Enabling IP forwarding..."
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    sysctl -p
    
    # Log successful startup
    log "Proxy setup completed successfully!"
    echo "Squid proxy started at $(date)" > /var/log/proxy-startup.log
    echo "Proxy is listening on port 3128" >> /var/log/proxy-startup.log
    
    # Get and log the proxy IP
    PROXY_IP=$(hostname -I | awk '{print $1}')
    log "Proxy internal IP: $PROXY_IP"
    echo "Proxy internal IP: $PROXY_IP" >> /var/log/proxy-startup.log
    
    # Monitor proxy health
    while true; do
      if systemctl is-active --quiet squid; then
        echo "Squid proxy is running at $(date)" >> /var/log/proxy-health.log
      else
        echo "Squid proxy is down at $(date), restarting..." >> /var/log/proxy-health.log
        systemctl restart squid
      fi
      sleep 60
    done &
  EOT

  service_account {
    scopes = ["cloud-platform"]
  }

  depends_on = [
    google_compute_subnetwork.subnet,
    google_compute_router_nat.nat
  ]
}

# Firewall rule to allow proxy traffic from subnet
resource "google_compute_firewall" "allow_proxy" {
  name    = "${var.vpc_network_name}-allow-proxy"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["3128"]
  }

  source_ranges = [var.vpc_subnet_cidr] # Use variable instead of hardcoded value
  target_tags   = ["proxy-server"]
  priority      = 1000

  description = "Allow proxy connections from VPC subnet"
}

# Output proxy details
output "proxy_configuration" {
  description = "HTTP proxy configuration details"
  value = {
    instance_name = google_compute_instance.proxy.name
    internal_ip   = google_compute_instance.proxy.network_interface[0].network_ip
    proxy_url     = "http://${google_compute_instance.proxy.network_interface[0].network_ip}:3128"
    zone          = google_compute_instance.proxy.zone
  }
}
