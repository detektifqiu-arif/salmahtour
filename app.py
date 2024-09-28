import os
import uuid
import json
import datetime
import requests
from flask import Flask, redirect, url_for, session, request, render_template, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from oauthlib.oauth2 import WebApplicationClient

# Izinkan penggunaan HTTP untuk pengembangan lokal
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Konfigurasi OAuth2 Google
client_id = "629677351136-2p8vqtuh01phju7d4g587u3pibvkr6ue.apps.googleusercontent.com"
client_secret = "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"
discovery_url = "https://accounts.google.com/.well-known/openid-configuration"
client = WebApplicationClient(client_id)

# Token API Telegram dan ID chat
telegram_bot_token = "7727363392:AAHwOfj2FTm9a6j30rlEu_iKSMBSZFofm7U"
telegram_chat_id = "935923063"

# Direktori untuk menyimpan file yang diunggah
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# File JSON untuk menyimpan data pengguna dan pembayaran
DATA_STORAGE_FILE = "user_data.json"
ID_STORAGE_FILE = "user_ids.json"
PAYMENT_STORAGE_FILE = "payment_data.json"

# Fungsi untuk mengecek ekstensi file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Fungsi untuk mendapatkan konfigurasi Google OAuth dari endpoint OpenID
def get_google_provider_cfg():
    return requests.get(discovery_url).json()

# Fungsi untuk memuat data pengguna dari file JSON
def load_user_data():
    if os.path.exists(DATA_STORAGE_FILE):
        with open(DATA_STORAGE_FILE, "r") as f:
            return json.load(f)
    return {}

# Fungsi untuk menyimpan data pengguna ke file JSON
def save_user_data(user_data):
    with open(DATA_STORAGE_FILE, "w") as f:
        json.dump(user_data, f)

# Fungsi untuk memuat data pembayaran dari file JSON
def load_payment_data():
    if os.path.exists(PAYMENT_STORAGE_FILE):
        with open(PAYMENT_STORAGE_FILE, "r") as f:
            return json.load(f)
    return {}

# Fungsi untuk menyimpan data pembayaran ke file JSON
def save_payment_data(payment_data):
    with open(PAYMENT_STORAGE_FILE, "w") as f:
        json.dump(payment_data, f)

# Fungsi untuk memformat angka dengan titik setiap 3 angka
def format_currency(amount):
    return f"{int(amount):,}".replace(",", ".")

# Fungsi untuk menghitung total pembayaran
def calculate_total_payment(payments):
    return sum([int(payment['nominal']) for payment in payments])

# Fungsi untuk memuat ID Primary dari file JSON
def load_user_ids():
    if os.path.exists(ID_STORAGE_FILE):
        with open(ID_STORAGE_FILE, "r") as f:
            return json.load(f)
    return {}

# Fungsi untuk menyimpan ID Primary ke file JSON
def save_user_ids(user_ids):
    with open(ID_STORAGE_FILE, "w") as f:
        json.dump(user_ids, f)

# Fungsi untuk mendapatkan atau membuat ID Primary berdasarkan email
def get_or_create_user_id(email):
    user_ids = load_user_ids()
    if email not in user_ids:
        user_ids[email] = str(uuid.uuid4())
        save_user_ids(user_ids)
    return user_ids[email]

# Menambahkan fungsi format_currency ke dalam template context
@app.context_processor
def utility_processor():
    return dict(format_currency=format_currency)

@app.route("/")
def index():
    if 'email' in session:
        user_data = load_user_data().get(session['email'], None)
        payments = load_payment_data().get(session['email'], [])
        total_pembayaran = calculate_total_payment(payments)
        return render_template("profile.html", email=session['email'], name=session['name'], user_id=session['user_id'], data=user_data, payments=payments, total_pembayaran=format_currency(total_pembayaran))
    return render_template("login.html")

# Rute untuk login dengan Google
@app.route("/login")
def login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
    )
    return redirect(request_uri)

# Rute callback setelah login Google berhasil
@app.route("/login/callback")
def callback():
    try:
        google_provider_cfg = get_google_provider_cfg()
        token_endpoint = google_provider_cfg["token_endpoint"]

        code = request.args.get("code")

        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url,
            redirect_url=request.base_url,
            code=code
        )

        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(client_id, client_secret),
        )

        token_data = token_response.json()
        client.parse_request_body_response(json.dumps(token_data))

        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers, data=body)

        userinfo = userinfo_response.json()

        if userinfo.get("email_verified"):
            session['email'] = userinfo["email"]
            session['name'] = userinfo["given_name"]

            session['user_id'] = get_or_create_user_id(session['email'])

            return redirect(url_for("profile"))
        else:
            return "Email tidak terverifikasi oleh Google.", 400

    except Exception as e:
        print(f"Terjadi kesalahan: {e}")
        return f"Terjadi kesalahan: {e}", 500

# Rute untuk menampilkan profil pengguna dengan form pengisian data
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if 'email' not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        # Validasi NIK hanya boleh angka
        nik = request.form.get("nik")
        if not nik.isdigit():
            flash("NIK hanya boleh berisi angka.")
            return redirect(url_for("profile"))

        # Ambil data dari form pengisian
        nama = request.form.get("nama")
        ayah = request.form.get("ayah")
        hp = request.form.get("hp")
        hp_keluarga = request.form.get("hp_keluarga")
        alamat = request.form.get("alamat")
        usia = request.form.get("usia")
        alergi = request.form.get("alergi")
        kursi_roda = request.form.get("kursi_roda")
        keberangkatan = request.form.get("keberangkatan")
        jenis_perjalanan = request.form.get("jenis_perjalanan")

        # Upload file foto KTP
        if 'ktp' not in request.files or request.files['ktp'].filename == '':
            flash("Harap unggah foto KTP.")
            return redirect(url_for("profile"))

        ktp_file = request.files['ktp']
        if ktp_file and allowed_file(ktp_file.filename):
            ktp_filename = secure_filename(ktp_file.filename)
            ktp_path = os.path.join(app.config['UPLOAD_FOLDER'], ktp_filename)
            ktp_file.save(ktp_path)
        else:
            flash("Ekstensi file tidak diperbolehkan.")
            return redirect(url_for("profile"))

        # Upload pass photo 3x4
        if 'pass_foto' not in request.files or request.files['pass_foto'].filename == '':
            flash("Harap unggah pass foto.")
            return redirect(url_for("profile"))

        pass_foto_file = request.files['pass_foto']
        if pass_foto_file and allowed_file(pass_foto_file.filename):
            pass_foto_filename = secure_filename(pass_foto_file.filename)
            pass_foto_path = os.path.join(app.config['UPLOAD_FOLDER'], pass_foto_filename)
            pass_foto_file.save(pass_foto_path)
        else:
            flash("Ekstensi file tidak diperbolehkan.")
            return redirect(url_for("profile"))

        # Simpan data pengguna ke file JSON
        user_data = load_user_data()
        user_data[session['email']] = {
            "NIK": nik,
            "Nama": nama,
            "Ayah": ayah,
            "HP": hp,
            "HP Keluarga": hp_keluarga,
            "Usia": usia,
            "Alamat": alamat,
            "Alergi": alergi,
            "KursiRoda": kursi_roda,
            "Keberangkatan": keberangkatan,
            "JenisPerjalanan": jenis_perjalanan,
            "Foto KTP": ktp_filename,
            "Pass Foto": pass_foto_filename
        }
        save_user_data(user_data)

        # Kirim pesan ke Telegram
        message = (f"📋 Data Pengguna:\n\nID: {session['user_id']}\nNama: {nama}\nEmail: {session['email']}\nNIK: {nik}\n"
                   f"Jenis Perjalanan: {jenis_perjalanan}\nKeberangkatan: {keberangkatan}\n"
                   f"Alamat: {alamat}\nAlergi Makanan: {alergi}\nKursi Roda: {kursi_roda}")

        send_message_to_telegram(message)

        # Kirim foto KTP dan pass photo ke Telegram
        send_photo_to_telegram(ktp_path)
        send_photo_to_telegram(pass_foto_path)

        flash("Data berhasil dikirim ke Telegram!")
        return redirect(url_for("profile"))

    user_data = load_user_data().get(session['email'], None)
    payments = load_payment_data().get(session['email'], [])
    total_pembayaran = calculate_total_payment(payments)
    return render_template("profile.html", email=session['email'], name=session['name'], user_id=session['user_id'], data=user_data, payments=payments, total_pembayaran=format_currency(total_pembayaran))

# Rute untuk menangani unggahan bukti pembayaran dan nominal pembayaran
@app.route("/upload_payment", methods=["POST"])
def upload_payment():
    if 'email' not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        nominal = request.form.get("nominal")
        if not nominal.isdigit():
            flash("Nominal hanya boleh berisi angka.")
            return redirect(url_for("profile"))

        # Upload file bukti pembayaran
        if 'bukti_pembayaran' not in request.files or request.files['bukti_pembayaran'].filename == '':
            flash("Harap unggah bukti pembayaran.")
            return redirect(url_for("profile"))

        pembayaran_file = request.files['bukti_pembayaran']
        if pembayaran_file and allowed_file(pembayaran_file.filename):
            bukti_pembayaran_filename = secure_filename(pembayaran_file.filename)
            bukti_pembayaran_path = os.path.join(app.config['UPLOAD_FOLDER'], bukti_pembayaran_filename)
            pembayaran_file.save(bukti_pembayaran_path)
        else:
            flash("Ekstensi file tidak diperbolehkan.")
            return redirect(url_for("profile"))

        # Dapatkan latitude dan longitude pengguna
        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")

        # Simpan bukti pembayaran ke file JSON
        payments = load_payment_data()
        payment_data = {
            "nominal": nominal,
            "bukti_pembayaran": bukti_pembayaran_filename,
            "tanggal": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if session['email'] not in payments:
            payments[session['email']] = []
        payments[session['email']].append(payment_data)
        save_payment_data(payments)

        # Hitung total pembayaran
        total_pembayaran = calculate_total_payment(payments[session['email']])

        # Kirim pesan ke Telegram
        google_maps_link = f"https://www.google.com/maps?q={latitude},{longitude}"
        message = (f"📋 Bukti Pembayaran Baru:\n\nID: {session['user_id']}\nEmail: {session['email']}\nNominal: Rp {nominal}\n"
                   f"Lokasi: [Google Maps Link]({google_maps_link})\nTanggal: {payment_data['tanggal']}\nTotal Pembayaran: Rp {total_pembayaran}")
        send_message_to_telegram(message)

        # Kirim bukti pembayaran ke Telegram
        send_photo_to_telegram(bukti_pembayaran_path)

        flash("Bukti pembayaran berhasil diunggah dan dikirim ke Telegram!")
        return redirect(url_for("profile"))

# Rute untuk menghapus riwayat pembayaran
@app.route("/delete_payment/<int:index>", methods=["POST"])
def delete_payment(index):
    if 'email' not in session:
        return redirect(url_for("login"))

    payments = load_payment_data()
    if session['email'] in payments and len(payments[session['email']]) > index:
        # Hapus pembayaran dari daftar
        deleted_payment = payments[session['email']][index]
        bukti_pembayaran_filename = deleted_payment['bukti_pembayaran']
        del payments[session['email']][index]
        save_payment_data(payments)

        # Hitung sisa total pembayaran
        total_pembayaran = calculate_total_payment(payments[session['email']])

        # Kirim pesan ke Telegram tentang penghapusan
        message = (f"📋 Pembayaran Dihapus:\n\nID: {session['user_id']}\nEmail: {session['email']}\nNominal: Rp {deleted_payment['nominal']}\n"
                   f"Total Pembayaran Tersisa: Rp {total_pembayaran}")
        send_message_to_telegram(message)

        # Kirim foto bukti pembayaran yang dihapus ke Telegram
        send_photo_to_telegram(os.path.join(app.config['UPLOAD_FOLDER'], bukti_pembayaran_filename))

        flash("Riwayat pembayaran berhasil dihapus.")
        return redirect(url_for("profile"))
    else:
        flash("Pembayaran tidak ditemukan.")
        return redirect(url_for("profile"))

# Fungsi untuk mengirim pesan ke Telegram
def send_message_to_telegram(message):
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    data = {
        "chat_id": telegram_chat_id,
        "text": message,
        "parse_mode": "Markdown"  # Agar bisa menggunakan link Google Maps
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("Pesan berhasil dikirim ke Telegram")
        else:
            print(f"Gagal mengirim pesan ke Telegram: {response.text}")
    except Exception as e:
        print(f"Error saat mengirim pesan ke Telegram: {e}")

# Fungsi untuk mengirim foto ke Telegram
def send_photo_to_telegram(photo_path):
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendPhoto"
    with open(photo_path, 'rb') as photo:
        data = {
            "chat_id": telegram_chat_id
        }
        files = {
            "photo": photo
        }
        try:
            response = requests.post(url, data=data, files=files)
            if response.status_code == 200:
                print("Foto berhasil dikirim ke Telegram")
            else:
                print(f"Gagal mengirim foto ke Telegram: {response.text}")
        except Exception as e:
            print(f"Error saat mengirim foto ke Telegram: {e}")

# Rute untuk logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# Fungsi untuk melayani file yang diunggah
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Jalankan aplikasi dengan mode debug
if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
