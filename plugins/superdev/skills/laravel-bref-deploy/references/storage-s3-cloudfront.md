# Storage — Public Assets on S3 + CloudFront, Uploads on an S3 Disk

This file OWNS public HTML/static-asset handling and user uploads on serverless Laravel (decision D8). The build skill does **not** own this — assets are a deploy-time concern because the Lambda filesystem is read-only. Read in Phase 4 of the deploy pipeline.

## The constraint that drives everything

The Lambda filesystem is **read-only except `/tmp`** (and `/tmp` is per-instance, ephemeral, and capped at 512 MB by default). That single fact dictates the whole storage model:

- You cannot `php artisan storage:link` and serve files from `public/storage` at runtime — `public/` is baked into the immutable deploy package and the symlink target is unwritable.
- You cannot write build artifacts, compiled assets, or user uploads to local disk and expect them to persist or be shared across the (many, concurrent, short-lived) Lambda instances.
- Anything a browser must fetch directly (CSS, JS, images, fonts, favicons) must live somewhere durable and public: **S3, fronted by CloudFront**.
- Anything user-generated (uploads, exports, generated PDFs) must live on an **S3 disk**, not local disk.

For an API-only Laravel backend (the default in `laravel-enterprise-backend`) there is very little static HTML — but `public/` still carries Bref's `index.php`, vendor-published assets, and any built frontend assets, and uploads are common. This file covers both.

## Two distinct jobs — do not conflate them

| Job | What it is | Where it lives | Served by |
|---|---|---|---|
| **Public static assets** | CSS/JS/images/fonts under `public/` (NOT `index.php`) | S3 bucket, synced **at deploy time** | CloudFront (via `ASSET_URL`) |
| **User uploads** | Files users upload at runtime; exports/PDFs the app generates | Same or separate S3 bucket, written **at runtime** via the `s3` Flysystem disk | Presigned S3 URLs or CloudFront |

The first is a one-way deploy-time `aws s3 sync`. The second is the framework's `Storage::disk('s3')` at runtime. They can share one bucket (prefix uploads under `uploads/`) or use two — two is cleaner for cache and ACL policy.

---

## Part 1 — Public static assets → S3, served via CloudFront

### Step 1: build assets locally, before packaging

Compile assets on the build host (CI or your machine), never on Lambda:

```bash
# In apps/api (or wherever your asset pipeline lives)
npm ci
npm run build          # Vite -> public/build/ (manifest + hashed files)
```

The hashed, fingerprinted output lands in `public/build/`. Everything under `public/` except `index.php` is a candidate for S3.

### Step 2: sync `public/` to S3 on deploy

After `osls deploy` (or `bref deploy`), push the static files to S3. The one command that owns this:

```bash
aws s3 sync public/ s3://app-api-assets-prod/ --exclude index.php
```

Why `--exclude index.php`: `public/index.php` is the **FPM entry point** that Bref runs inside the `web` Lambda. It must NOT be served from S3 — it is PHP, not a static file, and CloudFront would serve its source. Exclude it (and any other `.php`).

A more explicit sync that also sets long-lived caching on fingerprinted files:

```bash
# Hashed build assets — immutable, cache for a year
aws s3 sync public/build/ s3://app-api-assets-prod/build/ \
  --cache-control "public, max-age=31536000, immutable"

# Everything else under public/ except PHP entry points
aws s3 sync public/ s3://app-api-assets-prod/ \
  --exclude "index.php" --exclude "*.php" --exclude "build/*" \
  --cache-control "public, max-age=3600"
```

Run this as a post-deploy step (see `deploy-checklist.md`). It is idempotent — re-running only uploads changed files.

### Step 3: point `ASSET_URL` at CloudFront, always use `asset()`

Set `ASSET_URL` to the CloudFront distribution domain so every `asset()` / `mix()` / Vite helper emits a CloudFront URL instead of a same-Lambda path:

```bash
# .env.example / SSM — the CloudFront domain (or your custom CNAME)
ASSET_URL=https://d111111abcdef8.cloudfront.net
```

In `serverless.yml` this is wired through (see `serverless-yml.md`):

```yaml
provider:
  environment:
    ASSET_URL: ${env:ASSET_URL}   # CloudFront domain — makes asset() emit CDN URLs
```

Then **always** generate asset URLs through the helper — never hardcode `/build/...` or `url('/css/app.css')`:

```blade
{{-- Good — resolves to ASSET_URL (CloudFront) at render time --}}
<link rel="stylesheet" href="{{ asset('build/assets/app.css') }}">
<script src="{{ asset('build/assets/app.js') }}"></script>

{{-- With Vite, the directive reads ASSET_URL automatically --}}
@vite(['resources/css/app.css', 'resources/js/app.js'])
```

```php
// In code, anywhere you reference a static asset
$logoUrl = asset('images/logo.svg');   // -> https://d111111abcdef8.cloudfront.net/images/logo.svg
```

`asset()` prefixes `ASSET_URL` when it is set; with it unset Laravel falls back to the app URL (the Lambda), which would 404 because the file is not on the Lambda's disk. Setting `ASSET_URL` is what makes the whole scheme work.

### Step 4: invalidate CloudFront on deploy

CloudFront caches aggressively. Fingerprinted files (`build/assets/app.[hash].js`) never need invalidation — the hash changes the path. But unhashed files (`favicon.ico`, `robots.txt`, manually-named images) and the occasional cache-busting need an invalidation after each deploy:

```bash
aws cloudfront create-invalidation \
  --distribution-id E2QWERTYUIOP12 \
  --paths "/favicon.ico" "/robots.txt" "/images/*"
```

A blunt `--paths "/*"` invalidates everything (the first 1,000 paths/month are free). Prefer targeted paths in steady state; use `/*` only when you are unsure what changed. Wire this into the post-deploy checklist (`deploy-checklist.md`).

> Prefer fingerprinted asset filenames. If every changing asset is content-hashed, you essentially never need a broad invalidation — the only invalidations are for the handful of fixed-name files.

---

## Part 2 — User uploads on an S3 disk (`allowAcl: true`)

Runtime-written files (avatars, attachments, generated exports) go through Laravel's Flysystem `s3` disk — never local disk.

### `FILESYSTEM_DISK=s3`

```bash
# .env.example / SSM
FILESYSTEM_DISK=s3

AWS_BUCKET=app-api-uploads-prod
AWS_DEFAULT_REGION=us-east-1
AWS_USE_PATH_STYLE_ENDPOINT=false
# Credentials come from the Lambda execution role on AWS (no keys in env);
# locally, AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY point at a dev bucket or MinIO.
```

### `config/filesystems.php` — the `s3` disk

```php
// config/filesystems.php — 'disks' => [ ... ]
's3' => [
    'driver' => 's3',
    'key' => env('AWS_ACCESS_KEY_ID'),
    'secret' => env('AWS_SECRET_ACCESS_KEY'),
    'region' => env('AWS_DEFAULT_REGION'),
    'bucket' => env('AWS_BUCKET'),
    'url' => env('AWS_URL'),                 // optional: CloudFront domain for public reads
    'endpoint' => env('AWS_ENDPOINT'),       // for MinIO / LocalStack in dev
    'use_path_style_endpoint' => env('AWS_USE_PATH_STYLE_ENDPOINT', false),
    'throw' => true,                         // throw on Flysystem errors, don't return false
    'allowAcl' => true,                      // REQUIRED to set per-object ACLs (e.g. 'private'/'public')
    'visibility' => 'private',               // uploads default to private; presign to read
],
```

`allowAcl: true` is required for the Flysystem v3 AWS adapter to honor per-object ACL operations (`Storage::disk('s3')->put($path, $contents, 'private')` / `setVisibility()`). Without it, ACL calls are silently ignored and `visibility` mapping does not work — uploads end up with the bucket default, which is usually wrong. Keep `visibility` at `private` and presign reads; only mark genuinely public files `public`.

### Writing an upload at runtime

```php
// Store under a workspace-scoped, unguessable key; default private visibility
$path = $request->file('avatar')->store(
    "uploads/{$workspaceId}/avatars",   // never trust the client filename for the path
    's3'
);
// $path -> uploads/<workspace>/avatars/<random>.jpg  (private)
```

Never write to `storage_path()` / `public_path()` at runtime — those are read-only on Lambda. Always go through `Storage::disk('s3')`. The framework's `local` disk maps to the read-only package; only `/tmp` is writable and only for transient work within a single invocation.

---

## Part 3 — Presigned URLs for uploads > 4 MB (API Gateway payload cap)

API Gateway / Lambda has a **hard request payload limit of ~6 MB** (and httpApi practically ~4 MB after Base64 + headers overhead). Any upload that could exceed a few MB must NOT be POSTed through the Lambda — it would 413 before your code runs. Use **presigned S3 PUT URLs** so the browser uploads straight to S3, bypassing the API entirely.

### Issue a presigned upload URL

```php
// app/Http/Controllers/UploadController.php
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

public function presignUpload(\Illuminate\Http\Request $request)
{
    $request->validate([
        'filename'     => ['required', 'string', 'max:255'],
        'content_type' => ['required', 'string'],
    ]);

    $workspaceId = app('workspace.id');                 // see backend skill's tenancy scope
    $key = "uploads/{$workspaceId}/" . Str::uuid() . '/' . $request->string('filename');

    // Temporary signed PUT URL — client uploads the bytes directly to S3.
    $url = Storage::disk('s3')->temporaryUploadUrl(
        $key,
        now()->addMinutes(10),
        ['ContentType' => $request->string('content_type')],
    );

    return response()->json([
        'upload_url' => $url['url'],
        'headers'    => $url['headers'],
        'key'        => $key,                            // client returns this to confirm
    ]);
}
```

```php
// Issue a presigned GET (download) URL for a private object
public function presignDownload(string $key)
{
    return response()->json([
        'url' => Storage::disk('s3')->temporaryUrl($key, now()->addMinutes(15)),
    ]);
}
```

### Client flow (three steps)

1. Browser calls `POST /api/v1/uploads/presign` → gets `{ upload_url, headers, key }`.
2. Browser `PUT`s the file bytes **directly to `upload_url`** (S3), with the returned headers. The API never sees the bytes — no payload cap.
3. Browser calls `POST /api/v1/uploads/confirm` with `key`; the API validates the object exists, records the reference row, and returns the view shape.

This pattern is mandatory for anything over a few MB and recommended for **all** uploads — it keeps the request path cheap and avoids Lambda memory/time spent shuttling bytes.

---

## `serverless.yml` resources — S3 buckets + CloudFront

Add these to the `resources:` block referenced in `serverless-yml.md`. Two buckets (assets vs uploads) with a CloudFront distribution in front of the assets bucket via Origin Access Control.

```yaml
resources:
  Resources:
    # --- Public static assets bucket (synced at deploy time) ---
    AssetsBucket:
      Type: AWS::S3::Bucket
      Properties:
        BucketName: app-api-assets-${sls:stage}
        PublicAccessBlockConfiguration:        # bucket stays private; CloudFront reads via OAC
          BlockPublicAcls: true
          BlockPublicPolicy: true
          IgnorePublicAcls: true
          RestrictPublicBuckets: true

    # --- User uploads bucket (written at runtime via the s3 disk) ---
    UploadsBucket:
      Type: AWS::S3::Bucket
      Properties:
        BucketName: app-api-uploads-${sls:stage}
        PublicAccessBlockConfiguration:
          BlockPublicAcls: false               # allowAcl on the disk sets per-object ACLs
          BlockPublicPolicy: true
          IgnorePublicAcls: false
          RestrictPublicBuckets: true
        CorsConfiguration:                     # allow direct browser PUT via presigned URLs
          CorsRules:
            - AllowedMethods: [PUT, GET]
              AllowedOrigins: ['https://app.example.com']
              AllowedHeaders: ['*']
              MaxAge: 3000

    # --- CloudFront Origin Access Control: lets the distribution read the private bucket ---
    AssetsOac:
      Type: AWS::CloudFront::OriginAccessControl
      Properties:
        OriginAccessControlConfig:
          Name: app-api-assets-oac-${sls:stage}
          OriginAccessControlOriginType: s3
          SigningBehavior: always
          SigningProtocol: sigv4

    # --- CloudFront distribution in front of the assets bucket ---
    AssetsCdn:
      Type: AWS::CloudFront::Distribution
      Properties:
        DistributionConfig:
          Enabled: true
          DefaultCacheBehavior:
            TargetOriginId: assets-origin
            ViewerProtocolPolicy: redirect-to-https
            Compress: true
            # AWS managed "CachingOptimized" policy id
            CachePolicyId: 658327ea-f89d-4fab-a63d-7e88639e58f6
          Origins:
            - Id: assets-origin
              DomainName: !GetAtt AssetsBucket.RegionalDomainName
              OriginAccessControlId: !Ref AssetsOac
              S3OriginConfig:
                OriginAccessIdentity: ''       # empty when using OAC (not legacy OAI)

    # --- Bucket policy: allow only this CloudFront distribution to read the assets bucket ---
    AssetsBucketPolicy:
      Type: AWS::S3::BucketPolicy
      Properties:
        Bucket: !Ref AssetsBucket
        PolicyDocument:
          Statement:
            - Effect: Allow
              Principal:
                Service: cloudfront.amazonaws.com
              Action: s3:GetObject
              Resource: !Sub '${AssetsBucket.Arn}/*'
              Condition:
                StringEquals:
                  AWS:SourceArn: !Sub 'arn:aws:cloudfront::${aws:accountId}:distribution/${AssetsCdn}'

  Outputs:
    AssetsCdnDomain:
      Description: Set ASSET_URL to this (https://) for asset() to emit CloudFront URLs
      Value: !GetAtt AssetsCdn.DomainName
```

After the first deploy, read `AssetsCdnDomain` from the stack outputs, set `ASSET_URL=https://<that-domain>` in SSM, and redeploy (or set it before the first deploy if you pre-provision the distribution). The Lambda execution role also needs `s3:PutObject`/`s3:GetObject` on the uploads bucket — grant it via `provider.iam.role.statements` in `serverless.yml`:

```yaml
provider:
  iam:
    role:
      statements:
        - Effect: Allow
          Action: [s3:PutObject, s3:GetObject, s3:DeleteObject]
          Resource: !Sub '${UploadsBucket.Arn}/*'
```

> The `web` Lambda execution role must be allowed to presign and read/write the uploads bucket. `serverless-lift` does not manage these buckets (it manages the queue construct); they are plain CloudFormation resources here.

## Validation

- `asset('build/...')` in a rendered page resolves to the CloudFront domain, not the Lambda URL.
- `aws s3 sync public/ s3://<assets-bucket>/ --exclude index.php` ran post-deploy; `index.php` is **not** present in the bucket.
- A static asset URL loads from CloudFront over HTTPS (check the response headers for `x-cache` / `via: ... cloudfront`).
- An upload over 4 MB succeeds via the presigned PUT flow (direct to S3), and a < 4 MB direct upload to the API still works.
- `Storage::disk('s3')->put(...)` writes to the uploads bucket; no code writes to `storage_path()`/`public_path()` at runtime.
- CloudFront invalidation is part of the deploy run for unhashed files.

## Anti-patterns

- `php artisan storage:link` and serving `public/storage/*` from the Lambda. `public/` is read-only and not browser-reachable; the symlink target is unwritable. Use the `s3` disk + CloudFront.
- Hardcoding asset paths (`/build/app.js`, `url('/css/app.css')`) instead of `asset()`. They resolve to the Lambda, which has no static files to serve, and 404.
- Leaving `ASSET_URL` unset. `asset()` then points at the app URL (Lambda) and every asset 404s.
- POSTing large files through the API. Anything over ~4 MB will 413 at API Gateway before your controller runs. Use presigned S3 PUT URLs.
- Writing uploads/exports to `storage_path()` or `/tmp` for anything that must persist. `/tmp` is per-instance and ephemeral; local disk is read-only. Use `Storage::disk('s3')`.
- Omitting `allowAcl: true` on the `s3` disk, then calling `setVisibility()`/per-object ACLs. The ACL ops are silently ignored and visibility does not apply.
- Making the assets bucket public directly. Keep it private and serve via CloudFront with Origin Access Control (OAC) so you control caching, HTTPS, and access in one place.
- Forgetting to invalidate CloudFront after changing an unhashed file (`favicon.ico`, `robots.txt`). The old version serves until the cache TTL expires. Fingerprint assets to avoid this entirely.
- Syncing `index.php` (or any `.php`) to S3. CloudFront would expose PHP source and the FPM entry point must run on the `web` Lambda, not on the CDN.