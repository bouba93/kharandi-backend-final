# 🎓 Kharandi Backend Django v1.0

> Backend Django industriel pour Kharandi — plateforme éducative et marketplace guinéenne.  
> **Déployé sur Render.com (plan gratuit) — Sans Celery — Sans Redis — NimbaSMS synchrone**

---

## ⚡ Différences vs la v1 Flask

| Aspect | Flask v1 | Django v1.0 |
|---|---|---|
| SMS | NimbaSMS synchrone | NimbaSMS synchrone (inchangé) |
| Cache | In-memory (perd tout au restart) | Cache base de données PostgreSQL |
| Stock | Pas de protection race condition | `SELECT FOR UPDATE` — atomique |
| Commissions | Calculées côté client | Calculées + enregistrées en DB |
| Admin | Dashboard React à coder | Django Admin (Unfold) prêt à l'emploi |
| OTP | Dict Python (perd tout au restart) | Stockés en PostgreSQL |
| Audit | Aucun | django-auditlog automatique |
| Crons | APScheduler en mémoire | Endpoints HTTP (cron-job.org gratuit) |

---

## 🗂 Architecture

```
kharandi_v2/
├── config/
│   ├── settings.py          # Config Django (Render-ready, sans Celery)
│   ├── urls.py              # Routes principales
│   └── wsgi.py
│
├── kharandi/
│   ├── services/
│   │   └── sms.py           # Service NimbaSMS (synchrone, retry intégré)
│   │
│   ├── apps/
│   │   ├── accounts/        # Users, OTP SQL, JWT, Profils Tutor/Vendor
│   │   ├── marketplace/     # Produits, Stock atomique, Commandes, Avis
│   │   ├── payments/        # LengoPay, Transactions, Commissions, Factures PDF
│   │   ├── courses/         # Cours, Inscriptions, Notes, Progression
│   │   ├── notifications/   # Endpoints SMS NimbaSMS
│   │   ├── search/          # Full-text search PostgreSQL natif
│   │   ├── reports/         # PDF (ReportLab) + Excel (OpenPyXL)
│   │   ├── support/         # Tickets + workflow agent
│   │   └── ai_assistant/    # Karamö — Quotas DB + Cache DB
│   │
│   └── management/
│       └── commands/
│           ├── cleanup_otps.py
│           └── send_inactivity_reminders.py
│
├── manage.py
├── requirements.txt
├── build.sh                 # Script de build Render
├── render.yaml              # Config déploiement Render
└── .env.example
```

---

## 🚀 Déploiement sur Render.com (gratuit)

### 1. Préparer le repository

```bash
git init
git add .
git commit -m "Initial commit Kharandi Django v1.0"
git remote add origin https://github.com/votre-org/kharandi-backend.git
git push -u origin main
```

### 2. Créer les services sur Render

**Base de données PostgreSQL (gratuit)**
- Dashboard Render → New → PostgreSQL
- Name: `kharandi-db`
- Plan: Free
- Copier l'**Internal Database URL**

**Service Web**
- Dashboard Render → New → Web Service
- Connecter votre repo GitHub
- Environment: `Python 3`
- Build Command: `./build.sh`
- Start Command: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120`

### 3. Variables d'environnement Render

Dans "Environment" du service web, ajouter :

```
SECRET_KEY          = (générer avec python -c "import secrets; print(secrets.token_hex(50))")
DEBUG               = False
DATABASE_URL        = (Internal URL de votre PostgreSQL Render)
ALLOWED_HOSTS       = .onrender.com
NIMBA_SID           = votre_sid
NIMBA_TOKEN         = votre_token
NIMBA_SENDER        = Kharandi
LENGOPAY_SITE_ID    = VXQsfatrR3pVaSc8
LENGOPAY_LICENSE    = votre_license
COMMISSION_RATE     = 0.05
CLOUDINARY_CLOUD_NAME = votre_cloud
CLOUDINARY_API_KEY    = votre_key
CLOUDINARY_API_SECRET = votre_secret
AI_PROVIDER         = gemini
GEMINI_API_KEY      = votre_cle
AI_DAILY_LIMIT_FREE = 10
CRON_SECRET         = un_token_secret_pour_vos_crons
CORS_ALLOWED_ORIGINS = https://votre-frontend.com
```

### 4. Créer le superadmin (une seule fois)

Dans le shell Render (Dashboard → Shell) :
```bash
python manage.py createsuperuser
```

---

## 💻 Développement local

```bash
# 1. Cloner et créer l'environnement
git clone ...
cd kharandi_v2
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer l'environnement
cp .env.example .env
# Éditer .env — pour dev local utiliser sqlite:
# DATABASE_URL=sqlite:///kharandi_dev.db

# 4. Migrations + cache table
python manage.py migrate
python manage.py createcachetable

# 5. Superadmin
python manage.py createsuperuser

# 6. Lancer
python manage.py runserver
```

Admin accessible sur : **http://localhost:8000/admin/**

---

## ⏰ Crons (sans Celery)

Sur Render gratuit, les crons sont remplacés par des **endpoints HTTP** appelés depuis [cron-job.org](https://cron-job.org) (gratuit).

| Endpoint | Fréquence recommandée | Rôle |
|---|---|---|
| `GET /api/auth/admin/cron/cleanup-otp/?secret=CRON_SECRET` | Toutes les 10 min | Purge OTP expirés |
| `GET /api/auth/admin/cron/inactivity/?secret=CRON_SECRET` | Quotidien à 9h | SMS rappel utilisateurs inactifs |

**Configuration cron-job.org :**
1. Créer un compte sur cron-job.org (gratuit)
2. Nouveau cron job → URL = `https://votre-app.onrender.com/api/auth/admin/cron/cleanup-otp/?secret=VOTRE_CRON_SECRET`
3. Header optionnel : `X-Cron-Secret: VOTRE_CRON_SECRET`

---

## 📡 Endpoints API (résumé)

### Auth
```
POST /api/auth/register/               Inscription
POST /api/auth/login/                  Connexion → JWT
POST /api/auth/logout/                 Déconnexion (blacklist JWT)
POST /api/auth/otp/send/               Envoyer OTP NimbaSMS
POST /api/auth/otp/verify/             Vérifier OTP
POST /api/auth/otp/resend/             Renvoyer OTP
POST /api/auth/password/reset/         Demande reset par SMS
POST /api/auth/password/reset/confirm/ Confirmer reset
GET|PATCH /api/auth/profile/           Profil utilisateur
GET  /api/auth/tutors/                 Liste répétiteurs vérifiés
POST /api/auth/token/refresh/          Rafraîchir JWT
```

### Marketplace
```
GET  /api/marketplace/products/                    Liste (filtres: min_price, max_price, category, vendor_city, min_rating, has_stock)
POST /api/marketplace/products/                    Créer annonce (vendeurs KYC)
GET  /api/marketplace/products/{id}/               Détail produit
POST /api/marketplace/products/{id}/validate/      Valider/Rejeter (admin) → SMS vendeur
POST /api/marketplace/products/{id}/review/        Avis acheteur → SMS vendeur
GET  /api/marketplace/categories/                  Catégories
POST /api/marketplace/checkout/                    Commander (stock atomique SELECT FOR UPDATE)
GET  /api/marketplace/orders/                      Mes commandes
GET  /api/marketplace/orders/{id}/                 Détail commande
```

### Paiements
```
POST /api/payments/initiate/           Initier session LengoPay
POST /api/payments/callback/           Webhook LengoPay (auto → SMS + facture PDF)
GET  /api/payments/transactions/       Historique transactions
GET  /api/payments/invoice/{id}/       Télécharger facture PDF
GET  /api/payments/sms-balance/        Solde NimbaSMS (admin)
```

### Cours
```
GET  /api/courses/                              Liste cours (filtres: level, subject, is_free)
POST /api/courses/                              Créer cours (répétiteurs)
GET  /api/courses/{id}/                         Détail cours
POST /api/courses/{id}/enroll/                  S'inscrire → SMS répétiteur
GET  /api/courses/my-courses/                   Mes cours (élève)
GET  /api/courses/my-courses/as-tutor/          Mes cours (répétiteur)
GET  /api/courses/grades/                       Mes notes
PATCH /api/courses/enrollment/{id}/progress/    Mettre à jour la progression
```

### Notifications SMS
```
POST /api/notify/welcome/              SMS bienvenue
POST /api/notify/order-confirm/        SMS confirmation commande
POST /api/notify/order-shipped/        SMS expédition
POST /api/notify/order-delivered/      SMS livraison
POST /api/notify/points/              SMS points crédités
POST /api/notify/new-message/         SMS nouveau message
POST /api/notify/course-reminder/     SMS rappel cours
POST /api/notify/annonce-validated/   SMS annonce validée
POST /api/notify/account-suspended/   SMS suspension (admin)
POST /api/notify/new-student/         SMS nouvel élève
POST /api/notify/bulk/                Broadcast (max 500, admin)
POST /api/notify/custom/              SMS libre (admin)
GET  /api/notify/balance/             Solde NimbaSMS (admin)
```

### Recherche
```
GET /api/search/?q=maths&type=all|courses|products|tutors&limit=20
GET /api/search/suggest/?q=ma
```

### Rapports
```
POST /api/reports/transactions/pdf/    Relevé ventes PDF (vendeur)
POST /api/reports/bulletin/pdf/        Bulletin notes PDF (répétiteur)
POST /api/reports/stats/excel/         Stats plateforme Excel (admin)
GET  /api/reports/my-transactions/pdf/ Mes transactions PDF (utilisateur connecté)
```

### Support
```
GET|POST /api/support/tickets/              Liste / Créer ticket
GET|POST /api/support/tickets/{id}/         Détail + ajouter message
POST     /api/support/tickets/{id}/resolve/ Résoudre → SMS client
POST     /api/support/tickets/{id}/assign/  Assigner à soi-même (agent)
```

### IA Karamö
```
POST /api/ai/ask/                              Poser une question
GET  /api/ai/quota/                            Quota journalier restant
GET  /api/ai/conversations/                    Liste conversations
GET|DELETE /api/ai/conversations/{id}/         Détail / Supprimer conversation
```

---

## 🛡️ Sécurité

- **JWT** avec blacklist des refresh tokens à la déconnexion
- **Brute-force** : django-axes (5 tentatives → blocage 30 min)
- **Rate limiting** : OTP (5/min), IA (20/h), général (100/h anon, 1000/h user)
- **Stock atomique** : `SELECT FOR UPDATE` dans les transactions Django
- **Audit logs** : tous les changements sur User, Product, Order, Transaction tracés
- **HTTPS forcé** en production (HSTS, redirect SSL)
- **Commissions** calculées côté serveur uniquement (jamais côté client)

---

## 🤖 IA Karamö — Fonctionnement

```
Élève → POST /api/ai/ask/ → Cache DB (24h) → HIT: réponse immédiate (0 token)
                                            → MISS: Gemini/DeepSeek/Claude → Cache → Réponse
                          → Quota journalier vérifié (cache DB)
                          → Historique sauvegardé en base
```

Le cache évite de payer des tokens si deux élèves posent la même question dans les 24h.

---

## 📦 Technologies

| Composant | Technologie |
|---|---|
| Framework | Django 5.0 + DRF 3.15 |
| Auth | SimpleJWT avec blacklist |
| BDD | PostgreSQL (Render gratuit) |
| Cache | Django DatabaseCache (sans Redis) |
| SMS | NimbaSMS synchrone avec retry |
| Paiements | LengoPay |
| Médias | Cloudinary (plan gratuit) |
| Statiques | Whitenoise |
| Admin | Django Unfold |
| Audit | django-auditlog |
| PDF | ReportLab |
| Excel | OpenPyXL |
| IA | Gemini / DeepSeek / Claude |
| Déploiement | Render.com (plan gratuit) |
