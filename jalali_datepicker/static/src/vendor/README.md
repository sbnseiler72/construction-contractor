# Vendor Directory — JalaliDatePicker

Place the following two files from the `@majidh1/jalalidatepicker` npm package here:

    jalalidatepicker.min.js
    jalalidatepicker.min.css

## How to obtain the vendor files

### Option A: via npm (recommended)
```bash
npm install @majidh1/jalalidatepicker
cp node_modules/@majidh1/jalalidatepicker/dist/jalalidatepicker.min.js  ./
cp node_modules/@majidh1/jalalidatepicker/dist/jalalidatepicker.min.css ./
```

### Option B: Direct download from CDN
Download both files from:
  https://unpkg.com/@majidh1/jalalidatepicker/dist/jalalidatepicker.min.js
  https://unpkg.com/@majidh1/jalalidatepicker/dist/jalalidatepicker.min.css

## Why local vendor copy?
- Odoo's asset bundler fingerprints and concatenates all declared assets.
- CDN references are blocked by strict CSP policies common in production Odoo deployments.
- Local vendor files survive offline environments and air-gapped servers.

## Important
Do NOT commit these files to version control if your company policy restricts
third-party minified JS. Instead, add them to .gitignore and document the
installation step in your README.
