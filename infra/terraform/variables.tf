# =============================================================================
# Kairon Frete — Terraform input variables
# -----------------------------------------------------------------------------
# No secret defaults are declared here. Provide values via a gitignored
# terraform.tfvars file (see terraform.tfvars.example) or TF_VAR_* env vars.
# =============================================================================

# ------------------------------ Render ------------------------------ #
variable "render_api_key" {
  description = "Render API key (Account Settings -> API Keys). Used by the render provider to manage services."
  type        = string
  sensitive   = true
}

# ----------------------------- Supabase ----------------------------- #
variable "supabase_access_token" {
  description = "Supabase personal access token (Account -> Access Tokens). Authenticates the supabase provider."
  type        = string
  sensitive   = true
}

variable "supabase_org_id" {
  description = "Supabase organization slug/ID that will own the created project."
  type        = string
}

variable "supabase_db_password" {
  description = "Password for the managed Postgres instance created inside the Supabase project. Min 8 chars, store securely."
  type        = string
  sensitive   = true
}

# ---------------------------- Backblaze B2 -------------------------- #
variable "backblaze_key_id" {
  description = "Backblaze B2 application key ID (master or scoped) used by the b2 provider."
  type        = string
  sensitive   = true
}

variable "backblaze_application_key" {
  description = "Backblaze B2 application key secret paired with backblaze_key_id."
  type        = string
  sensitive   = true
}

# ------------------------------ Common ------------------------------ #
variable "region" {
  description = "Deployment region shorthand shared across providers (Render/Supabase). Map to provider-specific codes in main.tf."
  type        = string
  default     = "us-east"
}

variable "project_name" {
  description = "Base name used to derive resource names (Supabase project, B2 bucket, Render services)."
  type        = string
  default     = "kairon-frete"
}

variable "docker_hub_org" {
  description = "Docker Hub org/namespace that hosts the pushed images (kairon-api, kairon-ui, kairon-worker)."
  type        = string
  default     = "kaironstrategy"
}
