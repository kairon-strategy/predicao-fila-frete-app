# Kairon Frete — Infrastructure (Terraform)

This module provisions the managed backing services for Kairon Frete:

| Provider       | What it creates                                   | Role                          |
| -------------- | ------------------------------------------------- | ----------------------------- |
| Supabase       | A `supabase_project` (managed Postgres + Auth)    | Source-of-truth database + auth |
| Backblaze B2   | A private `b2_bucket`                              | Data lake (raw/processed data) |
| Render         | API web service, Prefect worker, Streamlit UI     | Application runtime            |

The Render services run the Docker images published by
`.github/workflows/deploy.yml` (`kaironstrategy/kairon-api|ui|worker`).

---

## 1. Prerequisites

You need accounts and credentials for **three** providers. If you don't have
them yet, `terraform plan` will fail at authentication — every provider needs a
valid token to read/plan remote state.

- **Render** — <https://render.com>
- **Supabase** — <https://supabase.com>
- **Backblaze B2** — <https://www.backblaze.com/cloud-storage>

Also install Terraform `>= 1.6`.

### How to obtain each credential

- **`render_api_key`** — Render dashboard → **Account Settings → API Keys →
  Create API Key**. Starts with `rnd_`.
- **`supabase_access_token`** — Supabase dashboard → **Account (top-right) →
  Access Tokens → Generate new token**. Starts with `sbp_`. This is a *personal
  access token*, not a project anon/service key.
- **`supabase_org_id`** — Supabase dashboard → **Organization → Settings**; use
  the organization slug/ID. The new project is created inside this org.
- **`supabase_db_password`** — you choose this. It becomes the Postgres
  superuser password for the managed database (min 8 chars, use a strong value).
- **`backblaze_key_id` / `backblaze_application_key`** — Backblaze dashboard →
  **App Keys → Add a New Application Key**. The **keyID** and **applicationKey**
  are shown once — copy both immediately (the secret is not shown again).

---

## 2. Configure variables

Copy the example file and fill in real values:

```bash
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars
```

`terraform.tfvars` is **gitignored** (the repo `.gitignore` ignores real
`*.tfvars` but keeps `*.tfvars.example`). Never commit real tokens.

Alternatively, export any variable as an environment variable, which is handy
for CI:

```bash
export TF_VAR_render_api_key="rnd_..."
export TF_VAR_supabase_access_token="sbp_..."
# ...etc
```

See `variables.tf` for the full list and descriptions.

---

## 3. Run Terraform

```bash
terraform init      # downloads providers, initializes the local backend
terraform plan      # requires VALID credentials for all three providers
terraform apply     # creates the resources
```

> **Note:** `terraform plan` is not offline — the Supabase, Render and
> Backblaze providers authenticate and query the remote APIs during planning.
> Without valid tokens the plan aborts. If you don't have accounts yet, create
> them first (Section 1).

To tear everything down:

```bash
terraform destroy
```

---

## 4. Pin provider versions after first init

`main.tf` uses **loose** version constraints on purpose so the first
`terraform init` can resolve compatible releases. Immediately afterwards, pin
each provider to the exact resolved version (read them from the generated
`.terraform.lock.hcl`) and update the `version = ...` lines in
`main.tf`. This keeps future plans reproducible. Tracked as `TODO(#22)`.

---

## 5. Things to reconcile with live provider docs

The community providers (`render-oss/render`, `Backblaze/b2`) change their
resource schemas over time. After `terraform init`, verify and adjust
(tracked as `TODO(#20)`):

- Render: resource/attribute names (`render_web_service`,
  `render_background_worker`, `runtime_source { image { ... } }`), the `plan`
  slug, whether `owner_id` is required on the provider, and the output URL
  attribute name.
- Supabase: valid `region` codes (consider `sa-east-1` / São Paulo for Brazil).
- Backblaze: server-side-encryption block shape and lifecycle rule field names.

---

## 6. State & secrets

The state backend is **local** (`terraform.tfstate`) for now — appropriate for a
solo operator. The state file contains secrets in plaintext and is gitignored.

To move to a shared, remote, S3-compatible backend on Backblaze B2 later, see
the commented `TODO(#21)` block in `main.tf`. State locking via DynamoDB is
**not** required (B2 has no DynamoDB); for a single operator, locking on an
S3-compatible store is optional.
