# Terraform Backend Configuration

terraform {
  backend "gcs" {
    # The bucket will be specified in the terraform init command or via environment variables
    # Example: terraform init -backend-config="bucket=your-project-terraform-state"
    prefix = "databricks-agent/vpc-infrastructure"
  }
}

# Note: To use this backend, you'll need to:
# 1. Create a GCS bucket for state storage:
#    gsutil mb gs://your-project-terraform-state
# 
# 2. Enable versioning on the bucket:
#    gsutil versioning set on gs://your-project-terraform-state
#
# 3. Initialize Terraform with the bucket:
#    terraform init -backend-config="bucket=your-project-terraform-state"
#
# Alternatively, you can set the TF_VAR_bucket environment variable
