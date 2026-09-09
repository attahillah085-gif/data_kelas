# 🛍️ The Girl House — Manajemen Bisnis Thrifting

Aplikasi web (PWA) untuk mengelola **bisnis thrifting baju** secara menyeluruh:
keuangan per periode, stok, jadwal konten, dan bagi hasil investor — dalam satu tempat
yang bisa **diakses banyak orang** (owner, pengelola, investor) dengan peran berbeda.

Dibangun sebagai **Progressive Web App**, sehingga bisa **dipasang ke HP** layaknya
aplikasi biasa dan mendukung **notifikasi push**. Tema warna **biru–putih soft** dengan
**mode gelap**.

> Repo ini sebelumnya berisi aplikasi kas kelas sederhana. File lama dipindahkan ke
> folder [`legacy/`](legacy/) sebagai arsip.

---

## ✨ Fitur

| Modul | Isi |
|-------|-----|
| **Dashboard** | Ringkasan KPI (pemasukan, pengeluaran, laba, nilai stok), grafik pemasukan vs pengeluaran, pengeluaran per kategori, transaksi & konten terbaru. Investor melihat estimasi bagi hasilnya sendiri. |
| **Keuangan per periode** | Buat periode (bulanan / per-batch), catat pemasukan & pengeluaran berkategori, laba bersih otomatis, tutup/buka periode. |
| **Inventori stok** | Kelola bal/karung thrift, harga modal & jual, progres terjual, laba per stok, dan **catat penjualan** yang otomatis jadi pemasukan di keuangan. |
| **Kalender konten** | Jadwalkan **live, video/reels, flyer, postingan**; tetapkan penanggung jawab; status rencana/selesai/batal; **pengingat otomatis** menjelang jadwal. |
| **Investor & bagi hasil** | Catat setoran modal, hitung kepemilikan (%), dan **simulasi bagi hasil per periode** sesuai proporsi modal. |
| **Notifikasi** | Notifikasi in-app + **Web Push** ke HP/desktop (opsional, via VAPID). |
| **Multi-user** | Peran **Owner** (akses penuh), **Pengelola** (kelola operasional), **Investor** (lihat laporan & bagi hasil). |

## 🎨 Teknologi

- **Backend:** Python + Flask + SQLAlchemy
- **Database:** SQLite (default, tanpa setup) — siap upgrade ke PostgreSQL
- **Auth:** Flask-Login (kata sandi di-hash)
- **Frontend:** HTML + CSS design system sendiri (tanpa framework berat) + sedikit JavaScript
- **PWA:** manifest, service worker (offline), install ke home screen, Web Push (VAPID)

---

## 🚀 Cara Menjalankan (lokal)

```bash
# 1. Buat virtual environment & pasang dependency
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. (Opsional) salin konfigurasi
cp .env.example .env                # lalu ganti SECRET_KEY

# 3. Isi data awal (akun owner + data demo)
python seed.py

# 4. Jalankan
python run.py
```

Buka **http://localhost:5000**

### Akun demo (dari `python seed.py`)

| Peran | Email | Kata sandi |
|-------|-------|-----------|
| Owner | `owner@thriftflow.id` | `owner123` |
| Pengelola | `pengelola@thriftflow.id` | `manager123` |
| Investor | `andi@thriftflow.id` | `invest123` |

> Tanpa menjalankan `seed.py`, aplikasi akan menampilkan halaman **setup** untuk membuat
> akun owner pertama saat pertama kali dibuka.

---

## 📱 Menjadikannya aplikasi (install ke HP)

Aplikasi ini sudah PWA. Buka lewat browser HP (via HTTPS di produksi) lalu pilih
**"Tambahkan ke layar utama"**. Ikonnya akan muncul seperti aplikasi biasa dan bisa
dibuka layar penuh.

### Mengaktifkan notifikasi push

```bash
# 1. Buat sepasang kunci VAPID
python seed.py --vapid

# 2. Tempel hasilnya ke file .env (VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT)
# 3. Restart aplikasi, buka halaman Notifikasi → "Aktifkan Notif HP"
```

**Pengingat konten** dibuat otomatis saat aplikasi diakses. Untuk pengingat yang benar-benar
terjadwal walau tidak ada yang membuka aplikasi, panggil endpoint berikut lewat cron:

```
GET /tasks/reminders?token=<SECRET_KEY>
```

---

## 🌐 Deploy ke produksi

1. Set environment variable `SECRET_KEY` (acak & panjang) dan, bila mau, `DATABASE_URL`
   (mis. PostgreSQL: `postgresql+psycopg://user:pass@host:5432/thriftflow`).
2. Jalankan dengan WSGI server:

   ```bash
   gunicorn "app:create_app()" -b 0.0.0.0:8000
   ```

3. Sajikan di belakang HTTPS (wajib untuk PWA & Web Push). Layanan seperti Railway,
   Render, atau VPS + Nginx cocok untuk ini.

> Catatan: workflow GitHub Pages bawaan (`.github/workflows/static.yml`) hanya untuk situs
> statis dan **tidak** cocok untuk aplikasi Flask ini — abaikan atau hapus bila tidak dipakai.

---

## 📁 Struktur proyek

```
app/
  __init__.py       # application factory
  config.py         # konfigurasi (env, database, VAPID)
  extensions.py     # db & login manager
  models.py         # model database
  utils.py          # decorator peran & filter format
  services.py       # notifikasi, push, bagi hasil, pengingat
  auth.py           # login / logout / setup awal
  main.py           # dashboard, pengaturan, manajemen pengguna
  finance.py        # periode & transaksi
  inventory.py      # stok thrift + catat penjualan
  content.py        # kalender konten
  investors.py      # investor & bagi hasil
  notifications.py  # notifikasi + Web Push
  templates/        # halaman (Jinja2)
  static/           # css, js, ikon, manifest, service worker
run.py              # entry pengembangan
seed.py             # data awal + generator VAPID
scripts/make_icons.py  # generator ikon PWA
requirements.txt
legacy/             # aplikasi kas lama (arsip)
```
