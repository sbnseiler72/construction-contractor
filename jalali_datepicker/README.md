# Jalali Date Picker — Odoo 19 Module

A lightweight Odoo 19 addon that provides a **Jalali (Shamsi/Persian)** date picker
field widget built on top of [JalaliDatePicker by majidh1](https://github.com/majidh1/JalaliDatePicker).

## Features

- Full Jalali calendar popup with RTL layout
- Transparent **Gregorian ↔ Jalali** conversion (Gregorian stored in DB)
- Min/max date constraints via `options`
- Nowruz holiday highlighting
- Readonly mode renders as plain span (no picker overhead in list/kanban)
- Manual keyboard input with blur-time validation
- Clear button when a value is set
- OWL 2 component — compatible with Odoo 19

---

## Installation

### 1. Place the vendor files

Download the JalaliDatePicker distribution files and place them at:

```
jalali_datepicker/static/src/vendor/jalalidatepicker.min.js
jalali_datepicker/static/src/vendor/jalalidatepicker.min.css
```

**Via npm:**
```bash
npm install @majidh1/jalalidatepicker
cp node_modules/@majidh1/jalalidatepicker/dist/jalalidatepicker.min.js \
   jalali_datepicker/static/src/vendor/
cp node_modules/@majidh1/jalalidatepicker/dist/jalalidatepicker.min.css \
   jalali_datepicker/static/src/vendor/
```

**Via CDN (for quick testing only):**
- https://unpkg.com/@majidh1/jalalidatepicker/dist/jalalidatepicker.min.js
- https://unpkg.com/@majidh1/jalalidatepicker/dist/jalalidatepicker.min.css

### 2. Copy addon to your addons path

```bash
cp -r jalali_datepicker /path/to/odoo/custom_addons/
```

### 3. Install in Odoo

```
Apps → Update App List → search "Jalali Date Picker" → Install
```

Or via CLI:
```bash
python odoo-bin -d your_db -i jalali_datepicker --stop-after-init
```

---

## Usage

Apply `widget="jalali_date"` to any `date` field in your form view:

```xml
<!-- Basic -->
<field name="date_order" widget="jalali_date"/>

<!-- With min/max constraints -->
<field
    name="deadline_date"
    widget="jalali_date"
    options="{'min_date': '2024-01-01', 'max_date': '2025-12-31'}"
/>

<!-- Disable holiday highlighting -->
<field
    name="birth_date"
    widget="jalali_date"
    options="{'highlight_holidays': false}"
/>
```

### Available Options

| Option | Type | Default | Description |
|---|---|---|---|
| `min_date` | string (Gregorian ISO) | `""` | Minimum selectable date |
| `max_date` | string (Gregorian ISO) | `""` | Maximum selectable date |
| `highlight_holidays` | bool | `true` | Highlight Nowruz (1 Farvardin) and first 4 days |

---

## Architecture

```
Database (Gregorian ISO)  ←→  Widget (Jalali display only)
       "2024-03-20"              "1403/01/01"
```

- The ORM always stores and queries **Gregorian** dates.
- Conversion is done entirely in the frontend widget using
  `jalaliDatepicker.toJalali()` and `jalaliDatepicker.toGregorian()`.
- Server-side `domain`, `onchange`, and reports are unaffected.

---

## File Structure

```
jalali_datepicker/
├── __init__.py
├── __manifest__.py
├── static/
│   └── src/
│       ├── js/
│       │   └── jalali_date_field.js       # OWL component + registry registration
│       ├── xml/
│       │   └── jalali_date_field.xml      # OWL QWeb template
│       └── vendor/
│           ├── README.md                  # Instructions to add vendor files
│           ├── jalalidatepicker.min.js    # ← ADD THIS (from npm)
│           └── jalalidatepicker.min.css   # ← ADD THIS (from npm)
└── views/
    └── usage_examples.xml                 # Documented usage examples
```

---

## Odoo Version Compatibility

| Odoo Version | Compatible |
|---|---|
| 19.0 | ✅ Yes (primary target) |
| 18.0 | ✅ Should work (OWL 2 + same field registry API) |
| 17.0 | ✅ Should work |
| 16.0 | ⚠️ Minor adjustments may be needed |
| ≤ 15.0 | ❌ No (OWL 1, different widget API) |

---

## License

LGPL-3
