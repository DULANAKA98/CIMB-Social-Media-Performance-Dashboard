# Deploying to AWS (low-cost setup, ~$15/month)

```
Browser ──▶ CloudFront ──/*──────▶ S3 bucket (frontend build)
                     └──/api/*──▶ Lightsail server: Caddy (HTTPS) ─▶ FastAPI ─▶ Postgres
                                                                       └──▶ Cloudflare insights worker
```

Files used: `backend/Dockerfile`, `deploy/docker-compose.yml`, `deploy/Caddyfile`,
`deploy/.env.example`, `.gitlab-ci.yml`.

Region: **Singapore (ap-southeast-1)**, the same region as the current Supabase database.

## Before you start

- An AWS account, and the AWS CLI on your laptop (`aws configure`).
- A hostname for the backend server, e.g. `api-origin.yourdomain.com`, whose DNS you can edit.
  No domain? Use `<static-ip-with-dashes>.sslip.io` (e.g. `13-250-1-2.sslip.io`); it needs no DNS setup.
- Generate three secrets now and keep them somewhere safe (a password manager):
  ```bash
  openssl rand -hex 24   # POSTGRES_PASSWORD
  openssl rand -hex 32   # ORIGIN_SECRET
  ```
  `FOLLOWER_REFRESH_SECRET` and the API keys come from `backend/cimb-dashboard-dev-backend.env`.

---

## Part 1: Lightsail server (backend + database)

### 1. Create the instance
Lightsail console → **Create instance**:
- Region: Singapore. Platform: Linux. Blueprint: **OS Only → Ubuntu 24.04 LTS**.
- Plan: **$12 (2 GB RAM, 60 GB SSD)**. Name: `cimb-dashboard`.

### 2. Networking
On the instance → **Networking** tab:
- **Attach a static IP** (free while attached).
- IPv4 firewall: keep **SSH 22** (restrict to your office IP if possible), add **HTTP 80** and **HTTPS 443**.

Then create a DNS **A record**: `api-origin.yourdomain.com → <static IP>` (skip if using sslip.io).

### 3. Turn on backups
Instance → **Snapshots** tab → enable **Automatic snapshots** (daily).

### 4. Install Docker
Connect with **SSH** (browser button or `ssh ubuntu@<static IP>`), then:
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
# 2 GB swap as a safety net for pandas-heavy requests
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo mkdir -p /opt/cimb && sudo chown ubuntu:ubuntu /opt/cimb
exit   # log out and back in so the docker group applies
```

### 5. Copy the code to the server
From your laptop, in the project folder:
```bash
rsync -az --exclude '*.env' --exclude 'venv/' --exclude '__pycache__/' \
  backend deploy ubuntu@<static IP>:/opt/cimb/
```

### 6. Create the server's settings file
On the server:
```bash
cd /opt/cimb/deploy
cp .env.example .env
nano .env        # fill in every value; ORIGIN_DOMAIN = your backend hostname
chmod 600 .env
```

### 7. Start the database and copy the data from Supabase
In Supabase → **Connect**, copy the **Session pooler** connection string (port **5432**, not 6543).
On the server:
```bash
cd /opt/cimb/deploy
docker compose up -d db

read -rs SUPABASE_URL   # paste the Supabase connection string, press Enter (not saved in history)
docker run --rm -v /tmp:/dump postgres:17-alpine \
  pg_dump "$SUPABASE_URL" --schema=public --no-owner --no-acl -Fc -f /dump/cimb.dump

docker compose cp /tmp/cimb.dump db:/tmp/cimb.dump
docker compose exec db pg_restore -U cimb -d cimb --no-owner --no-acl /tmp/cimb.dump
```
A few warnings about Supabase-only roles or extensions are normal. Check the data arrived:
```bash
docker compose exec db psql -U cimb -d cimb -c "select count(*) from posts;" \
  -c "select count(*) from follower_snapshots;"
```
Compare with the same counts in the Supabase SQL editor. Then `rm /tmp/cimb.dump`.

### 8. Start everything
```bash
docker compose up -d --build
curl -s http://127.0.0.1:8000/api/status            # should return JSON
curl -s -o /dev/null -w '%{http_code}\n' https://<ORIGIN_DOMAIN>/api/status   # should print 403
```
The `403` is correct: the backend only answers requests coming through CloudFront.
If HTTPS fails, check `docker compose logs caddy` (usually DNS not pointing at the static IP yet).

### 9. Daily follower refresh
On the server, `crontab -e`, add (01:00 UTC = 09:00 Malaysia time):
```
0 1 * * * curl -fsS -X POST http://127.0.0.1:8000/api/followers/refresh -H "X-Follower-Refresh-Secret: <FOLLOWER_REFRESH_SECRET>" >> /home/ubuntu/follower-refresh.log 2>&1
```

### 9b. Dashboard sign-in accounts
Every `/api` request (except the follower refresh above) needs a signed-in session, so the
backend refuses requests with `503` until these two settings are in `deploy/.env`:

1. On your laptop, in the project folder, create one entry per person (password at least 12
   characters, typed without being shown):
   ```bash
   python backend/hash_password.py
   ```
   It prints `username:pbkdf2_sha256....`. Only this salted hash is stored, never the password.
2. Create the session-signing secret:
   ```bash
   python backend/hash_password.py --secret
   ```
3. On the server, add both to `deploy/.env` (several users are joined with commas), then restart:
   ```
   DASHBOARD_USERS=alice:pbkdf2_sha256...,bob:pbkdf2_sha256...
   SESSION_SECRET=...
   ```
   ```bash
   cd /opt/cimb/deploy && docker compose up -d backend
   ```

Sessions last 12 hours. To remove someone, delete their entry; to reset a password, replace
their entry (their open sessions end at once). Changing `SESSION_SECRET` signs everyone out.
Ten wrong passwords for one username within 15 minutes lock that username for 15 minutes.

---

## Part 2: Frontend (S3 + CloudFront)

### 10. Create the S3 bucket
S3 console → **Create bucket**: name e.g. `cimb-dashboard-frontend`, region Singapore,
**Block all public access: ON**. Leave everything else default.

### 11. Create the CloudFront distribution
CloudFront console → **Create distribution** (if asked for a pricing plan, the free plan is enough):

**Origin 1 (frontend)**
- Origin: the S3 bucket. Origin access: **Origin access control (OAC)** → create new.
- After creating, CloudFront shows a **bucket policy**. Copy it into S3 → bucket → Permissions → Bucket policy.

**Default behavior** (frontend)
- Viewer protocol: **Redirect HTTP to HTTPS**. Cache policy: **CachingOptimized**.

**Settings**
- Default root object: `index.html`. WAF: **Do not enable** (saves cost).

**Origin 2 (backend)**: distribution → **Origins → Create origin**
- Origin domain: your `ORIGIN_DOMAIN`. Protocol: **HTTPS only**.
- **Add custom header**: name `X-Origin-Secret`, value = your `ORIGIN_SECRET`.
- Response timeout: **60** seconds (the maximum without a quota request).

**Behavior for the API**: distribution → **Behaviors → Create behavior**
- Path pattern: `/api/*`. Origin: origin 2.
- Viewer protocol: Redirect HTTP to HTTPS.
- Allowed methods: **GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE**.
- Cache policy: **CachingDisabled**. Origin request policy: **AllViewerExceptHostHeader**.

Note the distribution ID and the domain (`dxxxxxxxx.cloudfront.net`).

### 12. Build and upload the frontend
From your laptop:
```bash
cd frontend
npm ci
VITE_API_URL=/api npm run build
aws s3 sync dist s3://cimb-dashboard-frontend --delete
aws cloudfront create-invalidation --distribution-id <DISTRIBUTION_ID> --paths "/*"
```

### 13. Test
Open `https://dxxxxxxxx.cloudfront.net`. Check that the dashboard loads data, uploads work,
AI insights and chat answer, and exports download.

---

## Part 3: Automatic deploys from GitLab (optional)

`.gitlab-ci.yml` redeploys both parts whenever `main` changes. It needs a GitLab Runner;
check **Settings → CI/CD → Runners** in the GitLab project. Without one, repeat steps 5, 8 and 12 by hand.

### 14. AWS deploy user
IAM → **Users → Create user** `gitlab-deployer` with this inline policy, then create an access key:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::cimb-dashboard-frontend" },
    { "Effect": "Allow", "Action": ["s3:PutObject", "s3:DeleteObject", "s3:GetObject"], "Resource": "arn:aws:s3:::cimb-dashboard-frontend/*" },
    { "Effect": "Allow", "Action": ["cloudfront:CreateInvalidation"], "Resource": "arn:aws:cloudfront::<ACCOUNT_ID>:distribution/<DISTRIBUTION_ID>" }
  ]
}
```

### 15. SSH key for deploys
On your laptop:
```bash
ssh-keygen -t ed25519 -f gitlab-deploy -N "" -C gitlab-deploy
ssh-copy-id -i gitlab-deploy.pub ubuntu@<static IP>
ssh-keyscan <static IP>      # output = SSH_KNOWN_HOSTS
```

### 16. GitLab variables
GitLab project → **Settings → CI/CD → Variables** (tick **Protected** and **Masked** where allowed):

| Key | Value |
|---|---|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | from step 14 |
| `AWS_DEFAULT_REGION` | `ap-southeast-1` |
| `S3_BUCKET` | `cimb-dashboard-frontend` |
| `CLOUDFRONT_DISTRIBUTION_ID` | from step 11 |
| `SSH_HOST` / `SSH_USER` | static IP / `ubuntu` |
| `SSH_KNOWN_HOSTS` | output of `ssh-keyscan` |
| `SSH_PRIVATE_KEY` | contents of `gitlab-deploy`, **Type: File** |

Then delete the local `gitlab-deploy` private key file. Merging into `main` now deploys automatically.

---

## Part 4: Finish

17. **Budget alert**: AWS Billing → **Budgets → Create budget**, monthly, $25, email alert.
18. **Retire Supabase**: run on AWS for a week or two, then pause or delete the Supabase project.
19. The insights worker stays on Cloudflare; nothing changes there.

## Day-to-day commands (on the server, in `/opt/cimb/deploy`)

| Task | Command |
|---|---|
| See status | `docker compose ps` |
| Backend logs | `docker compose logs -f backend` |
| Restart backend | `docker compose restart backend` |
| Manual DB backup | `docker compose exec db pg_dump -U cimb -Fc cimb > ~/cimb-$(date +%F).dump` |
| OS updates (monthly) | `sudo apt update && sudo apt upgrade -y && sudo reboot` |
