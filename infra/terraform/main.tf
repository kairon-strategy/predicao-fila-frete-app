# =============================================================================
# Kairon Frete — Infrastructure as Code (root module)
# -----------------------------------------------------------------------------
# Provisions the managed backing services for the SaaS:
#   * Supabase  -> managed Postgres + Auth (source of truth)
#   * Backblaze -> B2 private bucket for the data lake
#   * Render    -> API web service, Prefect worker, Streamlit UI web service
#
# IMPORTANT: the resource/attribute schemas of the community providers below
# (especially render-oss/render and Backblaze/b2) evolve. Treat the blocks here
# as a best-effort starting point and reconcile them against the live provider
# docs after the first `terraform init`. See TODO(#20).
# =============================================================================

terraform {
  required_version = ">= 1.6"

  required_providers {
    # NOTE(versions): version constraints are intentionally loose here. After
    # the first `terraform init`, pin each provider to the exact version that
    # got resolved (copy from .terraform.lock.hcl) to keep plans reproducible.
    supabase = {
      source  = "supabase/supabase"
      version = ">= 1.0" # TODO(#22): pin exact version after `terraform init`
    }
    b2 = {
      source  = "Backblaze/b2"
      version = ">= 0.8" # TODO(#22): pin exact version after `terraform init`
    }
    render = {
      source  = "render-oss/render"
      version = ">= 1.0" # TODO(#22): pin exact version after `terraform init`
    }
  }

  # ---------------------------------------------------------------------------
  # State backend — local for now (solo dev, single operator).
  # ---------------------------------------------------------------------------
  # The local state file (terraform.tfstate) is gitignored. It contains
  # secrets in plaintext — keep it off shared machines / out of backups.
  #
  # TODO(#21): migrate to a remote, S3-compatible backend on Backblaze B2 once
  # more than one person touches infra. B2 exposes an S3-compatible endpoint,
  # so the standard `s3` backend works with a custom endpoint. Example:
  #
  #   terraform {
  #     backend "s3" {
  #       bucket = "kairon-frete-tfstate"          # a SEPARATE private bucket
  #       key    = "terraform/kairon-frete.tfstate"
  #       region = "us-east-005"                    # B2 region of the bucket
  #       endpoints = {
  #         s3 = "https://s3.us-east-005.backblazeb2.com"
  #       }
  #       access_key = "<B2_KEY_ID>"                # or via AWS_ACCESS_KEY_ID
  #       secret_key = "<B2_APP_KEY>"              # or via AWS_SECRET_ACCESS_KEY
  #       # B2's S3 API is not fully AWS-compatible; skip the AWS-only checks:
  #       skip_credentials_validation = true
  #       skip_metadata_api_check     = true
  #       skip_region_validation      = true
  #       skip_requesting_account_id  = true
  #       # State locking via DynamoDB is NOT used: B2 has no DynamoDB. For a
  #       # solo dev this is fine (no concurrent applies). Locking on an
  #       # S3-compatible store is optional; revisit if the team grows.
  #       use_lockfile = true                       # TF >= 1.10 native S3 lock
  #     }
  #   }
  #
  backend "local" {
    path = "terraform.tfstate"
  }
}

# =============================================================================
# Providers
# =============================================================================

provider "supabase" {
  access_token = var.supabase_access_token
}

provider "b2" {
  application_key_id = var.backblaze_key_id
  application_key    = var.backblaze_application_key
}

provider "render" {
  api_key = var.render_api_key
  # owner_id is often required by the render provider to scope resources to a
  # team/user. TODO(#20): set owner_id (Render dashboard -> Account settings)
  # if `terraform plan` reports it as required.
  # owner_id = "<your-render-owner-id>"
}

# =============================================================================
# Supabase — managed Postgres + Auth (the app's source of truth)
# =============================================================================
resource "supabase_project" "main" {
  organization_id   = var.supabase_org_id
  name              = var.project_name
  database_password = var.supabase_db_password

  # Supabase uses its own region codes (e.g. "us-east-1", "sa-east-1"). We map
  # the shared "us-east" shorthand here; for the Brazilian market you may prefer
  # "sa-east-1" (São Paulo) to cut latency. TODO(#20): confirm valid region
  # codes against Supabase docs.
  region = var.region == "us-east" ? "us-east-1" : var.region

  # NOTE: the connection string / anon+service keys are read AFTER creation from
  # the Supabase dashboard (or via the management API) and injected into Render
  # as SUPABASE_URL / SUPABASE_KEY / DATABASE_URL. They are deliberately not
  # wired here to avoid persisting service-role keys in Terraform state.
}

# =============================================================================
# Backblaze B2 — private data lake bucket
# =============================================================================
resource "b2_bucket" "data_lake" {
  bucket_name = "${var.project_name}-datalake"
  bucket_type = "allPrivate" # never public; access via app keys only

  # At-rest encryption: B2 supports SSE-B2 (server-side, B2-managed keys).
  # TODO(#20): enable once confirmed against the provider schema, e.g.:
  # default_server_side_encryption {
  #   mode      = "SSE-B2"
  #   algorithm = "AES256"
  # }

  # Lifecycle: expire/transition raw ingest after N days to control cost.
  # Adjust the retention window to your compliance needs.
  lifecycle_rules {
    file_name_prefix              = "raw/"
    days_from_hiding_to_deleting  = 30
    days_from_uploading_to_hiding = 90
  }
}

# =============================================================================
# Render — services (API web, Prefect worker, Streamlit UI web)
# -----------------------------------------------------------------------------
# These consume the Docker images published by .github/workflows/deploy.yml.
# The render-oss/render provider resource names/attributes below are the most
# plausible shape; TODO(#20): reconcile with provider docs after init.
# =============================================================================

locals {
  api_image    = "${var.docker_hub_org}/kairon-api:latest"
  ui_image     = "${var.docker_hub_org}/kairon-ui:latest"
  worker_image = "${var.docker_hub_org}/kairon-worker:latest"

  # Render region codes differ from the shared shorthand (e.g. "oregon",
  # "virginia", "frankfurt", "singapore"). Map "us-east" -> "virginia".
  render_region = var.region == "us-east" ? "virginia" : var.region
}

# --------------------------------- API ---------------------------------- #
resource "render_web_service" "api" {
  name   = "${var.project_name}-api"
  region = local.render_region
  plan   = "starter" # TODO(#20): confirm plan slug (free/starter/standard...)

  # Deploy from the prebuilt Docker Hub image rather than building on Render.
  runtime_source {
    image {
      image_url = local.api_image
    }
  }

  # Runtime secrets are set here as env vars. Feed them from TF variables or,
  # preferably, from Render's own secret store / dashboard to avoid state leaks.
  # TODO(#20): populate the full env (DATABASE_URL, REDIS_URL, ANTHROPIC_API_KEY,
  # SENTRY_DSN, SUPABASE_URL, SUPABASE_KEY, SUPABASE_JWT_SECRET, etc.).
  env_vars = {
    APP_ENV = { value = "production" }
    # DATABASE_URL = { value = "<from supabase_project.main>" }
  }

  health_check_path = "/health"
}

# ------------------------------- Worker --------------------------------- #
# Prefect worker: a background service (no public port, no health endpoint).
resource "render_background_worker" "worker" {
  name   = "${var.project_name}-worker"
  region = local.render_region
  plan   = "starter" # TODO(#20): confirm plan slug

  runtime_source {
    image {
      image_url = local.worker_image
    }
  }

  env_vars = {
    APP_ENV = { value = "production" }
  }
}

# --------------------------------- UI ----------------------------------- #
resource "render_web_service" "ui" {
  name   = "${var.project_name}-ui"
  region = local.render_region
  plan   = "starter" # TODO(#20): confirm plan slug

  runtime_source {
    image {
      image_url = local.ui_image
    }
  }

  env_vars = {
    APP_ENV = { value = "production" }
    # KAIRON_API_URL = { value = render_web_service.api.url }  # point UI at API
  }

  # Streamlit's health endpoint.
  health_check_path = "/_stcore/health"
}

# =============================================================================
# Outputs
# =============================================================================
output "supabase_project_id" {
  description = "ID of the created Supabase project (managed Postgres + Auth)."
  value       = supabase_project.main.id
}

output "data_lake_bucket_name" {
  description = "Name of the private Backblaze B2 data-lake bucket."
  value       = b2_bucket.data_lake.bucket_name
}

output "api_service_url" {
  description = "Public URL of the Render API web service."
  value       = render_web_service.api.url
  # TODO(#20): the URL attribute name may differ (e.g. `service_url`); adjust
  # after confirming the render provider schema.
}

output "ui_service_url" {
  description = "Public URL of the Render Streamlit UI web service."
  value       = render_web_service.ui.url
}
