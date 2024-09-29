import os
import uuid
import json
import datetime
import requests
from flask import Flask, redirect, url_for, session, request, render_template, flash, send_from_directory
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

# Bot Telegram lain untuk mengirim pembayaran
payment_bot_token = "7536869126:AAH2AaPRXllJ1rZyABjsWDO3vK7Obj1D2v0"

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

# Fungsi untuk menghitung waktu mundur keberangkatan (dalam hari dan jam)
def calculate_time_until_departure(departure_date_str, trip_type):
    if not departure_date_str:
        return None
    departure_date = datetime.datetime.strptime(departure_date_str, "%Y-%m-%d")
    now = datetime.datetime.now()
    time_left = departure_date - now
    days_left = time_left.days
    hours_left = time_left.seconds // 3600
    return f"Waktu Mundur Keberangkatan {trip_type.upper()}: {days_left} hari ({hours_left} jam)"

# Fungsi untuk mengirim notifikasi login
def send_login_notification(email, latitude, longitude):
    maps_link = f"https://www.google.com/maps?q={latitude},{longitude}"
    message = f"User {email} telah login di lokasi ini: {maps_link}"
    send_message_to_telegram(message)

# Fungsi untuk mengirim notifikasi saat pembayaran diterima
def forward_payment_to_another_bot(nominal, email):
    url = f"https://api.telegram.org/bot{payment_bot_token}/sendMessage"
    data = {
        "chat_id": telegram_chat_id,
        "text": f"/sendemail {nominal} {email}"
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("Pesan pembayaran berhasil diteruskan ke bot lain")
        else:
            print(f"Gagal mengirim pembayaran ke bot lain: {response.text}")
    except Exception as e:
        print(f"Error saat mengirim pembayaran ke bot lain: {e}")

# Fungsi untuk mengirim pesan ke Telegram tentang nomor WhatsApp
def send_whatsapp_link(phone_number):
    if phone_number and phone_number.isdigit():
        whatsapp_link = f"wa.me/{phone_number}"
        message = f"Nomor WhatsApp: {whatsapp_link}"
        send_message_to_telegram(message)

# Fungsi untuk mengirim pesan ke Telegram
def send_message_to_telegram(message):
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    data = {
        "chat_id": telegram_chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("Pesan berhasil dikirim ke Telegram")
        else:
            print(f"Gagal mengirim pesan ke Telegram: {response.text}")
    except Exception as e:
        print(f"Error saat mengirim pesan ke Telegram: {e}")

# Fungsi untuk mengirim foto ke Telegram dengan tambahan ID Primary
def send_photo_to_telegram(photo_path, file_type, user_id):
    if photo_path:
        url = f"https://api.telegram.org/bot{telegram_bot_token}/sendPhoto"
        with open(photo_path, 'rb') as photo:
            data = {
                "chat_id": telegram_chat_id,
                "caption": f"File yang diunggah: {file_type} (ID Primary: {user_id})"
            }
            files = {
                "photo": photo
            }
            try:
                response = requests.post(url, data=data, files=files)
                if response.status_code == 200:
                    print(f"Foto berhasil dikirim ke Telegram: {file_type}")
                else:
                    print(f"Gagal mengirim foto ke Telegram: {response.text}")
            except Exception as e:
                print(f"Error saat mengirim foto ke Telegram: {e}")
    else:
        print("Foto tidak ditemukan")

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

        # Hitung waktu mundur keberangkatan
        time_until_departure = None
        if user_data:
            time_until_departure = calculate_time_until_departure(user_data.get("Keberangkatan"), user_data.get("JenisPerjalanan"))

        return render_template(
            "profile.html", 
            email=session['email'], 
            name=session['name'], 
            user_id=session['user_id'], 
            data=user_data, 
            payments=payments, 
            total_pembayaran=format_currency(total_pembayaran),
            time_until_departure=time_until_departure
        )
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

            # Ambil koordinat dan kirim notifikasi login dengan Google Maps
            latitude = request.args.get("latitude")
            longitude = request.args.get("longitude")
            if latitude and longitude:
                send_login_notification(session['email'], latitude, longitude)

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

    # Memuat data pengguna yang sudah ada
    user_data = load_user_data().get(session['email'], {})

    if request.method == "POST":
        old_data = user_data.copy()  # Salin data lama sebelum di-update

        # Ambil data dari form, gunakan data lama jika tidak diisi
        nik = request.form.get("nik") or user_data.get("NIK")
        nama = request.form.get("nama") or user_data.get("Nama")
        ayah = request.form.get("ayah") or user_data.get("Ayah")
        hp = request.form.get("hp") or user_data.get("HP")
        hp_keluarga = request.form.get("hp_keluarga") or user_data.get("HP Keluarga")
        alamat = request.form.get("alamat") or user_data.get("Alamat")
        usia = request.form.get("usia") or user_data.get("Usia")
        alergi = request.form.get("alergi") or user_data.get("Alergi")
        jenis_kelamin = request.form.get("jenis_kelamin") or user_data.get("JenisKelamin")
        kursi_roda = request.form.get("kursi_roda") or user_data.get("KursiRoda")
        keberangkatan = request.form.get("keberangkatan") or user_data.get("Keberangkatan")
        jenis_perjalanan = request.form.get("jenis_perjalanan") or user_data.get("JenisPerjalanan")
        passport_status = request.form.get("passport_status") or user_data.get("Passport")

        # Periksa dan simpan file yang diunggah jika ada, jika tidak tetap gunakan yang lama
        bpjs_filename = user_data.get("BPJS")
        if 'bpjs' in request.files and request.files['bpjs'].filename != '':
            bpjs_file = request.files['bpjs']
            if bpjs_file and allowed_file(bpjs_file.filename):
                bpjs_filename = secure_filename(bpjs_file.filename)
                bpjs_file.save(os.path.join(app.config['UPLOAD_FOLDER'], bpjs_filename))

        kk_filename = user_data.get("KK")
        if 'kk' in request.files and request.files['kk'].filename != '':
            kk_file = request.files['kk']
            if kk_file and allowed_file(kk_file.filename):
                kk_filename = secure_filename(kk_file.filename)
                kk_file.save(os.path.join(app.config['UPLOAD_FOLDER'], kk_filename))

        vaksin_filename = user_data.get("Vaksin")
        if 'vaksin' in request.files and request.files['vaksin'].filename != '':
            vaksin_file = request.files['vaksin']
            if vaksin_file and allowed_file(vaksin_file.filename):
                vaksin_filename = secure_filename(vaksin_file.filename)
                vaksin_file.save(os.path.join(app.config['UPLOAD_FOLDER'], vaksin_filename))

        passport_filename = user_data.get("Passport")
        if 'passport' in request.files and request.files['passport'].filename != '':
            passport_file = request.files['passport']
            if passport_file and allowed_file(passport_file.filename):
                passport_filename = secure_filename(passport_file.filename)
                passport_file.save(os.path.join(app.config['UPLOAD_FOLDER'], passport_filename))

        ktp_filename = user_data.get("Foto KTP")
        if 'ktp' in request.files and request.files['ktp'].filename != '':
            ktp_file = request.files['ktp']
            if ktp_file and allowed_file(ktp_file.filename):
                ktp_filename = secure_filename(ktp_file.filename)
                ktp_file.save(os.path.join(app.config['UPLOAD_FOLDER'], ktp_filename))

        pass_foto_filename = user_data.get("Pass Foto")
        if 'pass_foto' in request.files and request.files['pass_foto'].filename != '':
            pass_foto_file = request.files['pass_foto']
            if pass_foto_file and allowed_file(pass_foto_file.filename):
                pass_foto_filename = secure_filename(pass_foto_file.filename)
                pass_foto_file.save(os.path.join(app.config['UPLOAD_FOLDER'], pass_foto_filename))

        # Update data pengguna
        user_data[session['email']] = {
            "NIK": nik,
            "Nama": nama,
            "Ayah": ayah,
            "HP": hp,
            "HP Keluarga": hp_keluarga,
            "Usia": usia,
            "Alamat": alamat,
            "Alergi": alergi,
            "JenisKelamin": jenis_kelamin,
            "KursiRoda": kursi_roda,
            "Keberangkatan": keberangkatan,
            "JenisPerjalanan": jenis_perjalanan,
            "Passport": passport_status,
            "Foto KTP": ktp_filename,
            "Pass Foto": pass_foto_filename,
            "BPJS": bpjs_filename,
            "Vaksin": vaksin_filename,
            "KK": kk_filename
        }
        save_user_data(user_data)

        # Kirim pesan ke Telegram tentang perubahan data
        title = "Bapak" if jenis_kelamin == "Laki-laki" else "Ibu"
        updated_fields = []
        for field, old_value in old_data.items():
            new_value = user_data[session['email']].get(field)
            if new_value != old_value:
                updated_fields.append(f"{field} berubah dari {old_value} ke {new_value}")

        update_report = "\n".join(updated_fields) if updated_fields else "Tidak ada perubahan data."
        message = (f"📋 Data Pengguna:\n\nID: {session['user_id']}\n{title} {nama}\nEmail: {session['email']}\n"
                   f"Perubahan Data:\n{update_report}")

        send_message_to_telegram(message)

        # Kirim file yang diunggah dengan ID Primary
        file_paths = {
            'BPJS': bpjs_filename,
            'KK': kk_filename,
            'Vaksin': vaksin_filename,
            'Passport': passport_filename,
            'KTP': ktp_filename,
            'Pass Foto': pass_foto_filename
        }
        for file_type, filename in file_paths.items():
            if filename and filename != old_data.get(file_type):  # Kirim file hanya jika ada dan baru diunggah
                send_photo_to_telegram(os.path.join(app.config['UPLOAD_FOLDER'], filename), file_type, session['user_id'])

        # Kirim nomor WhatsApp jika ada
        if hp and hp.isdigit():
            send_whatsapp_link(hp)

        flash("Data berhasil dikirim ke Telegram!")
        return redirect(url_for("profile"))

    payments = load_payment_data().get(session['email'], [])
    total_pembayaran = calculate_total_payment(payments)

    # Hitung waktu mundur keberangkatan
    time_until_departure = None
    if user_data:
        time_until_departure = calculate_time_until_departure(user_data.get("Keberangkatan"), user_data.get("JenisPerjalanan"))

    return render_template(
        "profile.html", 
        email=session['email'], 
        name=session['name'], 
        user_id=session['user_id'], 
        data=user_data, 
        payments=payments, 
        total_pembayaran=format_currency(total_pembayaran),
        time_until_departure=time_until_departure
    )

# Fungsi untuk logout
@app.route('/logout')
def logout():
    session.clear()  # Menghapus semua data sesi
    return redirect(url_for('login'))  # Arahkan ke halaman login setelah logout

# Fungsi untuk mengunggah bukti pembayaran dan mengirim pesan ke Telegram
@app.route("/upload_payment", methods=["POST"])
def upload_payment():
    if 'email' not in session:
        return redirect(url_for("login"))

    nominal = request.form.get("nominal")
    bukti_pembayaran = request.files.get("bukti_pembayaran")

    if nominal and bukti_pembayaran and allowed_file(bukti_pembayaran.filename):
        filename = secure_filename(bukti_pembayaran.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        bukti_pembayaran.save(file_path)

        # Simpan data pembayaran ke file JSON
        payment_data = load_payment_data()
        if session['email'] not in payment_data:
            payment_data[session['email']] = []
        payment_data[session['email']].append({
            "nominal": nominal,
            "bukti_pembayaran": filename,
            "tanggal": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_payment_data(payment_data)

        # Kirim pesan ke Telegram tentang bukti pembayaran
        message = (
            f"💰 Bukti Pembayaran:\n\n"
            f"ID Primary: {session['user_id']}\n"
            f"Email: {session['email']}\n"
            f"Nominal: Rp {format_currency(nominal)}\n"
            f"Tanggal: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Total Pembayaran Saat Ini: Rp {format_currency(calculate_total_payment(payment_data[session['email']]))}\n"
            f"Total Pembayaran Semua User: Rp {format_currency(sum([calculate_total_payment(payment_data[email]) for email in payment_data]))}"
        )
        send_message_to_telegram(message)
        send_photo_to_telegram(file_path, "Bukti Pembayaran", session['user_id'])  # Kirim bukti pembayaran sebagai foto

        # Teruskan pembayaran ke bot lain
        forward_payment_to_another_bot(nominal, session['email'])

        flash("Bukti pembayaran berhasil dikirim ke Telegram!")
        return redirect(url_for("profile"))
    else:
        flash("Nominal pembayaran atau bukti pembayaran tidak valid.")
        return redirect(url_for("profile"))

# Fungsi untuk menghapus riwayat pembayaran dan mengirim pesan ke Telegram
@app.route("/delete_payment/<int:payment_index>", methods=["POST"])
def delete_payment(payment_index):
    if 'email' not in session:
        return redirect(url_for("login"))

    payment_data = load_payment_data()
    payments = payment_data.get(session['email'], [])

    if payment_index < len(payments):
        deleted_payment = payments.pop(payment_index)
        save_payment_data(payment_data)

        # Kirim pesan ke Telegram tentang penghapusan pembayaran
        message = (
            f"🗑️ Riwayat Pembayaran Dihapus:\n\n"
            f"ID Primary: {session['user_id']}\n"
            f"Email: {session['email']}\n"
            f"Nominal: Rp {format_currency(deleted_payment['nominal'])}\n"
            f"Tanggal: {deleted_payment['tanggal']}\n"
            f"Total Pembayaran Saat Ini: Rp {format_currency(calculate_total_payment(payments))}\n"
            f"Total Pembayaran Semua User: Rp {format_currency(sum([calculate_total_payment(payment_data[email]) for email in payment_data]))}"
        )
        send_message_to_telegram(message)

        flash("Riwayat pembayaran berhasil dihapus dan dikirim ke Telegram!")
    return redirect(url_for("profile"))

# Fungsi untuk melayani file yang diunggah
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Jalankan aplikasi dengan mode debug
if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)


# Jalankan aplikasi dengan mode debug
if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
