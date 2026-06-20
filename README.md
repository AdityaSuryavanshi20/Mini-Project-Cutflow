# CutFlow – Fenestration ERP

## Production-grade Django ERP for aluminium/uPVC window & door fabrication

---

## Architecture Overview

```
CutFlow/
├── CutFlow/          # Django project config (settings, urls, wsgi)
├── accounts/         # Users, roles (admin/salesman/production/viewer), activity log
├── catalog/          # Systems, profiles, profile formulas, glass, hardware, company settings
├── projects/         # Customers, projects, measurements (site survey items)
├── quotations/       # Quotations, line items, PDF generation
├── production/       # Production jobs, cut computation, bar optimization, offcut tracking
├── core/             # Dashboard, formula engine, optimizer, middleware, seed command
└── templates/        # All HTML templates
```

### Business Flow
1. **Salesman** creates customer → project → adds measurements
2. **Salesman** generates quotation from measurements → sets rates → downloads PDF → sends to customer
3. **Admin** locks project after acceptance
4. **Production** creates production job → generates cut items (via formula engine) → runs bar optimization → downloads cutting list PDF
5. **Production** tracks hardware BOQ, glass schedule, reusable offcuts

---

## Requirements

```
Python 3.10+
MySQL 8.0+
```

---

## Installation

### 1. MySQL Database Setup

```sql
CREATE DATABASE cutflow_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'cutflow_user'@'localhost' IDENTIFIED BY 'your_strong_password';
GRANT ALL PRIVILEGES ON cutflow_db.* TO 'cutflow_user'@'localhost';
FLUSH PRIVILEGES;
```

### 2. Python Environment

```bash
cd CutFlow
python -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in `CutFlow/` (next to `manage.py`):

```env
SECRET_KEY=your-very-long-random-secret-key-minimum-50-chars
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

DB_NAME=cutflow_db
DB_USER=cutflow_user
DB_PASSWORD=your_strong_password
DB_HOST=localhost
DB_PORT=3306

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=CutFlow <noreply@yourdomain.com>

COMPANY_NAME=Your Company Name
```

> For development, `DEBUG=True` and skip email settings.

### 4. Run Migrations

```bash
python manage.py migrate
```

### 5. Create Superuser (Admin)

```bash
python manage.py createsuperuser
```
Enter username, email, password. This user gets admin access automatically via Django admin.

**Then set their role** – go to `/admin/accounts/userprofile/` and set role = `admin`.

### 6. Seed Initial Catalog Data

```bash
python manage.py seed_data
```

This seeds:
- 8 window/door systems (SY01–SY08)
- 12 aluminium profiles with formulas for SY01
- 8 glass types (clear, toughened, DGU etc.)
- 35+ hardware items (hinges, handles, locks, accessories)
- Hardware rules for SY01 Casement
- Company settings (edit via `/admin/catalog/companysettings/`)

### 7. Collect Static Files (Production Only)

```bash
python manage.py collectstatic --noinput
```

### 8. Run Development Server

```bash
python manage.py runserver
```

Access at: **http://127.0.0.1:8000/**

---

## Production Deployment (Gunicorn + Nginx)

```bash
# Start Gunicorn
gunicorn CutFlow.wsgi:application \
    --workers 4 \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /var/log/cutflow/access.log \
    --error-logfile /var/log/cutflow/error.log \
    --daemon
```

Sample Nginx config:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location /static/ {
        alias /path/to/CutFlow/staticfiles/;
    }
    location /media/ {
        alias /path/to/CutFlow/media/;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## User Roles

| Role       | Access |
|------------|--------|
| `admin`    | Full access; lock/unlock projects; Django admin |
| `salesman` | Customers, projects, measurements, quotations |
| `production` | Production jobs, optimization, cutting lists |
| `viewer`   | Read-only dashboard |

---

## Adding Profile Formulas

Formulas are defined in Django Admin → **Catalog → Profile Formulas**.

### Formula Variables

| Variable | Meaning |
|----------|---------|
| `W` | Window width in mm |
| `H` | Window height in mm |
| `n_panels` | Number of sashes/panels |
| `offset_l` | Profile left offset (from Profile record) |
| `offset_r` | Profile right offset |
| `offset_t` | Profile top offset |
| `offset_b` | Profile bottom offset |
| `qty` | Unit quantity |

### Example Formulas

```
Frame width top/bottom:       W
Frame height left/right:      H
T-Sash width (2 pieces):      W - offset_l - offset_r    qty: n_panels
T-Sash height (2 pieces):     H - offset_t - offset_b    qty: n_panels
Transom/Mullion width:        W - offset_l - offset_r    qty: 1
Bay facet coupler:            635                          qty: 2
```

---

## Key URLs

| URL | Description |
|-----|-------------|
| `/` | Dashboard |
| `/accounts/login/` | Login |
| `/projects/` | Project list |
| `/projects/new/` | Create project |
| `/projects/customers/` | Customer list |
| `/quotations/` | All quotations |
| `/quotations/<id>/pdf/` | Download quotation PDF |
| `/production/` | Production jobs |
| `/production/<id>/optimize/` | Run bar optimization |
| `/production/<id>/cutting-list.pdf` | Download cutting list PDF |
| `/catalog/systems/` | Systems catalog |
| `/admin/` | Django admin (admin role only) |

---

## PDF Reports Generated

1. **Quotation PDF** – Customer-facing, matches Windowmaker Sales Line format
   - Company letterhead + logo
   - Customer address / delivery address
   - Line items with dimensions, glass, color
   - Pricing: subtotal, discount, installation, freight, GST, grand total
   - Payment terms & T&Cs

2. **Cutting List PDF** – Production workshop format
   - Per-profile sections
   - Bar assignments with cut lengths, angles, position codes
   - Waste and offcut tracking
   - Matches Windowmaker Optimised Cutting List layout

---

## Extending the System

### Add a new System with Formulas
1. Go to `/admin/catalog/system/add/`
2. Add profiles at `/admin/catalog/profile/add/`
3. Add formulas at `/admin/catalog/profileformula/add/`
   - One formula per (profile, system, position) combination

### Customize Company Settings
- `/admin/catalog/companysettings/` → Edit name, address, GST rates, bar length, kerf, etc.

### Hardware Rules
- `/admin/catalog/systemhardwarerule/` → Define how many hardware pieces each system needs

---

## SQL Schema Summary

Tables created by migrations:
- `accounts_userprofile` – user roles
- `accounts_activitylog` – audit trail
- `catalog_brand`, `catalog_color`
- `catalog_system`, `catalog_profile`, `catalog_profileformula`
- `catalog_glass`, `catalog_hardware`, `catalog_systemhardwarerule`
- `catalog_companysettings`
- `projects_customer`, `projects_project`, `projects_projectstatushistory`
- `projects_measurementitem`
- `quotations_quotation`, `quotations_quotationitem`
- `production_productionjob`, `production_productionitem`
- `production_productioncutitem`, `production_hardwarerequirement`
- `production_optimizationrun`, `production_optimizationsegment`
- `production_optimizedcut`, `production_reusableoffcut`

---

## Commands Reference

```bash
# Apply migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Seed catalog data
python manage.py seed_data

# Run dev server
python manage.py runserver

# Collect static (production)
python manage.py collectstatic --noinput

# Shell for debugging
python manage.py shell
```
