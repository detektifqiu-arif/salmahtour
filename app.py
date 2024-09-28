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

        # Hitung total akumulasi pembayaran seluruh pengguna
        all_payments = load_payment_data()
        total_akumulasi = calculate_total_payment([payment for user_payments in all_payments.values() for payment in user_payments])

        # Kirim pesan ke Telegram
        google_maps_link = f"https://www.google.com/maps?q={latitude},{longitude}"
        message = (f"📋 Bukti Pembayaran Baru:\n\nID: {session['user_id']}\nEmail: {session['email']}\nNominal: Rp {format_currency(nominal)}\n"
                   f"Lokasi: [Google Maps Link]({google_maps_link})\nTanggal: {payment_data['tanggal']}\nTotal Pembayaran: Rp {format_currency(total_pembayaran)}\n"
                   f"Total Akumulasi Semua Pembayaran: Rp {format_currency(total_akumulasi)}")
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

        # Hitung total akumulasi pembayaran seluruh pengguna
        all_payments = load_payment_data()
        total_akumulasi = calculate_total_payment([payment for user_payments in all_payments.values() for payment in user_payments])

        # Kirim pesan ke Telegram tentang penghapusan
        message = (f"📋 Pembayaran Dihapus:\n\nID: {session['user_id']}\nEmail: {session['email']}\nNominal: Rp {format_currency(deleted_payment['nominal'])}\n"
                   f"Total Pembayaran Tersisa: Rp {format_currency(total_pembayaran)}\n"
                   f"Total Akumulasi Semua Pembayaran: Rp {format_currency(total_akumulasi)}")
        send_message_to_telegram(message)

        # Kirim foto bukti pembayaran yang dihapus ke Telegram
        send_photo_to_telegram(os.path.join(app.config['UPLOAD_FOLDER'], bukti_pembayaran_filename))

        flash("Riwayat pembayaran berhasil dihapus.")
        return redirect(url_for("profile"))
    else:
        flash("Pembayaran tidak ditemukan.")
        return redirect(url_for("profile"))
