# 🚀 Panduan Meng-online-kan The Girl House

Aplikasi ini butuh **hosting** agar bisa diakses lewat internet. Semua file konfigurasi
sudah disiapkan — Anda tinggal ikuti salah satu cara di bawah. **HTTPS otomatis aktif**
di kedua layanan ini (wajib agar PWA bisa di-install & notifikasi jalan).

> Butuh: akun GitHub (repo ini) + akun di layanan hosting. Ada paket **gratis**.

Pilih salah satu:
- **PythonAnywhere** — GRATIS, **tanpa kartu kredit**, dapat link online (di bawah). ⭐ paling pas.
- **Hostinger VPS** — cocok untuk dipakai bisnis, always-on, data permanen.
- **Render** — cepat, tapi paket gratisnya kini minta verifikasi kartu.

> ⚠️ **Hostinger shared hosting / public_html TIDAK bisa** menjalankan aplikasi ini
> (itu untuk PHP/WordPress). Pakai PythonAnywhere (gratis) atau VPS.

---

## ⭐ PythonAnywhere (GRATIS, tanpa kartu kredit)

Cara termudah online tanpa bayar & tanpa kartu. Dapat link `namaanda.pythonanywhere.com`.

1. **Daftar** di **https://www.pythonanywhere.com** → pilih akun **Beginner (Free)**.
2. Buka tab **Consoles** → **Bash**. Ambil kode:
   ```bash
   git clone https://github.com/attahillah085-gif/data_kelas.git
   cd data_kelas
   python3.11 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
3. Buka tab **Web** → **Add a new web app** → **Manual configuration** → **Python 3.11**.
4. Di halaman konfigurasi web, isi:
   - **Source code:** `/home/NAMAANDA/data_kelas`
   - **Working directory:** `/home/NAMAANDA/data_kelas`
   - **Virtualenv:** `/home/NAMAANDA/data_kelas/.venv`
   *(ganti `NAMAANDA` dengan username PythonAnywhere Anda)*
5. Klik link file **WSGI configuration**, hapus isinya, ganti dengan:
   ```python
   import os, sys
   path = '/home/NAMAANDA/data_kelas'
   if path not in sys.path:
       sys.path.insert(0, path)
   os.environ['SECRET_KEY'] = 'GANTI-dengan-teks-acak-panjang'
   os.environ['COOKIE_SECURE'] = '1'
   from app import create_app
   application = create_app()
   ```
6. Di bagian **Static files**, tambahkan: URL `/static/` → Directory `/home/NAMAANDA/data_kelas/app/static`.
7. Klik tombol hijau **Reload**. Buka `https://NAMAANDA.pythonanywhere.com`.
   → Halaman **Setup** muncul → buat akun **pengelola** pertama. Selesai! 🎉

**Update ke versi terbaru nanti:** di console Bash →
```bash
cd data_kelas && git pull && .venv/bin/pip install -r requirements.txt
```
lalu klik **Reload** di tab Web. (Data Anda aman — tidak terhapus.)

> Catatan paket gratis: 1 web app, kuota CPU harian wajar untuk toko kecil, dan
> app perlu di-"Run until 3 months" (klik tombol perpanjang tiap 3 bulan di tab Web).
> Domain sendiri (mis. thegirlhouse.com) tersedia di paket berbayar.

---

## 🏆 Hostinger VPS (untuk dipakai bisnis)

> ⚠️ **Beli paket VPS**, mis. **KVM 1/KVM 2** — **BUKAN** hosting biasa/WordPress.
> Hosting shared hanya untuk PHP dan **tidak bisa** menjalankan aplikasi Python ini.

### Langkah
1. **Beli VPS** di Hostinger → saat setup pilih OS **Ubuntu 22.04/24.04**. Catat **IP VPS**
   dan **password root** (atau atur SSH key).
2. **(Disarankan) Arahkan domain** ke VPS: di pengaturan DNS domain, buat **A record**
   ke IP VPS (mis. `app.thegirlhouse.id → 123.45.67.89`). Domain diperlukan agar **HTTPS**
   aktif (wajib untuk PWA & notifikasi). Belum punya domain? Bisa dulu tanpa (akses via IP),
   HTTPS dipasang belakangan.
3. **Masuk ke VPS** lewat SSH (atau Browser Terminal di panel Hostinger):
   ```bash
   ssh root@IP-VPS-ANDA
   ```
4. **Jalankan pemasangan otomatis** (ganti dengan domain kamu; kosongkan bila belum ada domain):
   ```bash
   apt update && apt install -y git
   git clone --branch claude/thrifting-business-management-ew0pt2 \
     https://github.com/attahillah085-gif/data_kelas.git /var/www/thegirlhouse
   sudo bash /var/www/thegirlhouse/deploy/setup_vps.sh app.domain-anda.com
   ```
   Skrip ini otomatis: pasang Python & Nginx, siapkan aplikasi, buat `SECRET_KEY`,
   nyalakan service, dan pasang **HTTPS gratis** (Let's Encrypt).
5. Buka **https://app.domain-anda.com** (atau `http://IP-VPS`) → halaman **Setup** muncul →
   buat **akun pemilik**. Selesai! 🎉

> **Repo privat?** Saat `git clone`, GitHub akan minta login. Pakai **username + Personal
> Access Token** GitHub, atau set repo jadi publik (aman — file rahasia `.env` tidak ikut
> ter-commit). Alternatif: unggah file lewat File Manager Hostinger ke `/var/www/thegirlhouse`.

### Merawat
- **Update ke versi terbaru:** `sudo bash /var/www/thegirlhouse/deploy/update.sh`
- **Restart:** `systemctl restart thegirlhouse`
- **Lihat log:** `journalctl -u thegirlhouse -f`
- **Backup data:** cukup salin file `/var/www/thegirlhouse/instance/thriftflow.db`

### Catatan data
Default memakai **SQLite** — datanya tersimpan permanen di file server (aman untuk tim
kecil). Untuk skala besar, pasang PostgreSQL lalu isi `DATABASE_URL` di `.env` dan restart.

---

## ✅ Cara termudah — Render (untuk coba/demo gratis)

1. Buka **https://render.com** → daftar/login (bisa pakai akun GitHub).
2. Klik **New +** → **Blueprint**.
3. Hubungkan & pilih repository **`data_kelas`**, lalu pilih branch
   **`claude/thrifting-business-management-ew0pt2`** (atau `main` bila sudah di-merge).
4. Render membaca file `render.yaml` dan otomatis menyiapkan:
   - Web service **the-girl-house**
   - Database **PostgreSQL** gratis (data tersimpan permanen)
   - `SECRET_KEY` acak
5. Klik **Apply / Create**. Tunggu ~2–4 menit sampai status **Live**.
6. Buka URL yang diberikan (mis. `https://the-girl-house.onrender.com`).
   Halaman **Setup** muncul → buat **akun pemilik** pertama. Selesai! 🎉

> Catatan: paket gratis Render "tidur" saat tidak ada pengunjung, jadi kunjungan pertama
> setelah idle agak lambat (~30 detik). Naik ke paket berbayar untuk selalu aktif.

### 🌐 Pakai domain Hostinger Anda di Render

Sudah punya domain di Hostinger? Pakai untuk aplikasi ini (lebih profesional daripada
`*.onrender.com`). Disarankan memakai **subdomain**, mis. `app.domain-anda.com`.

1. Di **Render** → buka service **the-girl-house** → **Settings** → **Custom Domains**
   → **Add Custom Domain** → ketik `app.domain-anda.com` → Render menampilkan **nilai CNAME**
   (mis. `the-girl-house.onrender.com`).
2. Di **Hostinger hPanel** → **Domains** → pilih domain → **DNS / Name Servers** → **DNS Zone**
   → **Manage** → tambah record:
   - **Type:** `CNAME`
   - **Name/Host:** `app`
   - **Target/Value:** `the-girl-house.onrender.com` (nilai dari Render tadi)
   - **TTL:** biarkan default
3. Simpan. Tunggu 5–30 menit (propagasi DNS). Render otomatis memasang **HTTPS gratis**.
   Selesai — buka `https://app.domain-anda.com` 🎉

> **Ingin pakai domain utama tanpa `app.` (mis. `domain-anda.com`)?** Render akan memberi
> **A record** (alamat IP) untuk domain utama — tambahkan sebagai record `A` dengan Name `@`
> di DNS Zone Hostinger. Subdomain (CNAME) lebih mudah, jadi disarankan itu dulu.

> **Catatan penting (paket gratis):** database Postgres gratis Render **kadaluarsa setelah
> 90 hari**. Sebelum itu, upgrade database ke paket berbayar agar **data tidak hilang**.
> Untuk bisnis yang sudah jalan, pertimbangkan langsung paket berbayar (~$7/bln).

---

## ✅ Alternatif — Railway

1. Buka **https://railway.app** → login dengan GitHub.
2. **New Project** → **Deploy from GitHub repo** → pilih `data_kelas`.
3. Tambahkan database: **New** → **Database** → **PostgreSQL**.
4. Buka service aplikasi → tab **Variables**, tambahkan:
   - `SECRET_KEY` = (teks acak panjang; buat dengan `python -c "import secrets;print(secrets.token_hex(32))"`)
   - `DATABASE_URL` = ambil dari database Postgres (Railway biasanya mengisinya otomatis;
     bila belum, salin `DATABASE_URL` milik service Postgres).
5. Railway otomatis menjalankan `Procfile`. Setelah **Deploy** sukses, buka domain publiknya
   (tab **Settings → Networking → Generate Domain**).
6. Buka domainnya → halaman **Setup** → buat akun pemilik. Selesai! 🎉

---

## 🔔 Mengaktifkan notifikasi push (opsional, bisa nanti)

1. Di komputer lokal: `python seed.py --vapid` → menghasilkan `VAPID_PUBLIC_KEY` &
   `VAPID_PRIVATE_KEY`.
2. Tempel keduanya sebagai **environment variable** di dashboard hosting (Render/Railway),
   lalu **redeploy**.
3. Di aplikasi → halaman **Notifikasi** → **Aktifkan Notif HP**.

## ⏰ Pengingat konten terjadwal (opsional)

Agar pengingat tetap terkirim walau tak ada yang membuka aplikasi, panggil endpoint ini
secara berkala (mis. via **cron-job.org** gratis, tiap 15 menit):

```
https://DOMAIN-ANDA/tasks/reminders?token=SECRET_KEY_ANDA
```

---

## ❓ Sering ditanya

- **Data hilang saat update?** Tidak, selama pakai **PostgreSQL** (Render blueprint &
  Railway sudah pakai Postgres). Hindari SQLite untuk produksi karena filesystem hosting
  bersifat sementara.
- **Menambah pengguna (pengelola/investor)?** Login sebagai owner → menu **Tim & Pengguna**.
- **Ganti nama/tagline/porsi bagi hasil?** Menu **Pengaturan**.
- **Pakai domain sendiri (mis. thegirlhouse.id)?** Bisa, atur di menu *Custom Domain*
  pada dashboard Render/Railway.
