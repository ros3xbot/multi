import requests, time
from random import randint

from app2.config.imports import *
from app2.client.purchase.balance import settlement_balance
from app.type_dict import PaymentItem
from app2.menus.util import (
    clear_screen,
    pause,
    print_panel,
    get_rupiah,
    display_html,
    simple_number,
    delay_inline,
    format_quota_byte
)

from app2.client.purchase.redeem import settlement_bounty
from app2.client.store.redeemables import get_redeemables

console = Console()


pending_redeems = []

def redeem_all_visible(pause_on_success=True, delay_seconds=0):
    theme = get_theme()
    api_key = AuthInstance.api_key
    tokens: dict = AuthInstance.get_active_tokens() or {}

    redeemables_res = get_redeemables(api_key, tokens, False)
    if not redeemables_res or redeemables_res.get("status") != "SUCCESS":
        print_panel("Informasi", "Tidak ada redeemables tersedia.")
        pause()
        return

    categories = redeemables_res.get("data", {}).get("categories", [])
    packages = {}
    # tampilkan daftar redeemables
    for i, cat in enumerate(categories):
        letter = chr(65 + i)
        for j, r in enumerate(cat.get("redeemables", [])):
            code = f"{letter}{j+1}"
            packages[code.lower()] = r
            console.print(f"{code} → {r.get('name')} ({r.get('action_type')})")

    choice = console.input("Pilih kode redeemable (misal A1): ").strip().lower()
    selected = packages.get(choice)
    if not selected:
        print_panel("Kesalahan", "Pilihan tidak valid.")
        return

    action_type = selected.get("action_type")
    action_param = selected.get("action_param")
    item_name = selected.get("name", "N/A")

    if action_type == "PDP":
        pkg = get_package(api_key, tokens, action_param)
        if not pkg:
            print_panel("Kesalahan", "Gagal ambil detail paket.")
            return
        option = pkg.get("package_option", {}) or {}
        console.print(f"Opsi paket: {option.get('name')} - Rp{get_rupiah(option.get('price',0))}")
        confirm = console.input("Claim paket ini? (y/n): ").lower()
        if confirm == "y":
            res = settlement_bounty(
                api_key=api_key,
                tokens=tokens,
                token_confirmation=pkg.get("token_confirmation", ""),
                ts_to_sign=pkg.get("timestamp", ""),
                payment_target=action_param,
                price=option.get("price", 0),
                item_name=item_name,
            )
            console.print(f"Status: {res.get('status')}")

    elif action_type == "PLP":
        family_data = get_family(api_key, tokens, action_param)
        if not family_data:
            print_panel("Kesalahan", "Gagal ambil data family.")
            return

        options = []
        for v in family_data.get("package_variants", []):
            for opt in v.get("package_options", []):
                family = family_data.get("package_family", {}) or {}
                if (family.get("payment_for") or "BUY_PACKAGE") == "REDEEM_VOUCHER":
                    options.append(opt)

        if not options:
            print_panel("Informasi", "Tidak ada opsi redeemable di family ini.")
            return

        for opt in options:
            console.print(f"{opt['order']} → {opt['name']} - Rp{get_rupiah(opt['price'])}")
        order = int(console.input("Pilih order option: ") or options[0]["order"])
        target_opt = next((o for o in options if o["order"] == order), None)
        if not target_opt:
            print_panel("Kesalahan", "Option tidak valid.")
            return

        res = settlement_bounty(
            api_key=api_key,
            tokens=tokens,
            token_confirmation=family_data.get("token_confirmation", ""),
            ts_to_sign=family_data.get("timestamp", ""),
            payment_target=target_opt["package_option_code"],
            price=target_opt["price"],
            item_name=target_opt["name"],
        )
        console.print(f"Status: {res.get('status')}")

    else:
        print_panel("Informasi", f"Tipe {action_type} tidak didukung.")

    pause()



def purchase_loop(
    family_code: str,
    order: int,
    use_decoy: bool,
    delay: int,
    pause_on_success: bool = False,
):
    theme = get_theme()
    ensure_git()
    api_key = AuthInstance.api_key
    tokens: dict = AuthInstance.get_active_tokens() or {}

    family_data = get_family(api_key, tokens, family_code)
    if not family_data:
        print_panel("Peringatan", f"Gagal mengambil data family untuk kode: {family_code}")
        pause()
        return False

    target_variant = None
    target_option = None
    for variant in family_data["package_variants"]:
        for option in variant["package_options"]:
            if option["order"] == order:
                target_variant = variant
                target_option = option
                break
        if target_option:
            break

    if not target_option or not target_variant:
        print_panel("Peringatan", f"Option order {order} tidak ditemukan pada family {family_code}")
        pause()
        return False

    option_name = target_option["name"]
    option_price = target_option["price"]
    variant_code = target_variant["package_variant_code"]

    console.rule()
    console.print(f"[{theme['text_title']}]Proses pembelian: {target_variant['name']} - {order}. {option_name} - Rp{option_price}[/]")

    decoy_package_detail = None
    if use_decoy:
        decoy = DecoyInstance.get_decoy("balance")
        decoy_package_detail = get_package(api_key, tokens, decoy["option_code"])
        if not decoy_package_detail:
            print_panel("Peringatan", "Gagal memuat detail paket decoy")
            pause()
            return False

    try:
        target_package_detail = get_package_details(
            api_key,
            tokens,
            family_code,
            variant_code,
            order,
            None,
            None,
        )
    except Exception as e:
        print_panel("Kesalahan", f"Terjadi error saat mengambil detail paket: {e}")
        delay_inline(delay)
        return True

    payment_items = [
        PaymentItem(
            item_code=target_package_detail["package_option"]["package_option_code"],
            product_type="",
            item_price=target_package_detail["package_option"]["price"],
            item_name=f"{randint(1000, 9999)} {target_package_detail['package_option']['name']}",
            tax=0,
            token_confirmation=target_package_detail["token_confirmation"],
        )
    ]

    if use_decoy and decoy_package_detail:
        payment_items.append(
            PaymentItem(
                item_code=decoy_package_detail["package_option"]["package_option_code"],
                product_type="",
                item_price=decoy_package_detail["package_option"]["price"],
                item_name=f"{randint(1000, 9999)} {decoy_package_detail['package_option']['name']}",
                tax=0,
                token_confirmation=decoy_package_detail["token_confirmation"],
            )
        )

    overwrite_amount = target_package_detail["package_option"]["price"]
    if use_decoy and decoy_package_detail:
        overwrite_amount += decoy_package_detail["package_option"]["price"]

    try:
        res = settlement_balance(
            api_key,
            tokens,
            payment_items,
            "BUY_PACKAGE",
            False,
            overwrite_amount,
        )

        if res and res.get("status", "") != "SUCCESS":
            error_msg = res.get("message", "Unknown error")
            if "Bizz-err.Amount.Total" in error_msg:
                error_msg_arr = error_msg.split("=")
                valid_amount = int(error_msg_arr[1].strip())
                print_panel("Informasi", f"Total amount disesuaikan menjadi: {valid_amount}")
                res = settlement_balance(
                    api_key,
                    tokens,
                    payment_items,
                    "BUY_PACKAGE",
                    False,
                    valid_amount,
                )

        if res and res.get("status", "") == "SUCCESS":
            print_panel("Sukses", "Pembelian berhasil")
            if pause_on_success:
                choice = console.input("Apakah ingin melanjutkan? (y/n): ").strip().lower()
                if choice == 'n':
                    return False

    except Exception as e:
        print_panel("Kesalahan", f"Terjadi error saat membuat order: {e}")

    if delay > 0:
        delay_inline(delay)

    return True


def purchase_by_family(
    family_code: str,
    use_decoy: bool,
    pause_on_success: bool = True,
    delay_seconds: int = 0,
    start_from_option: int = 1,
):
    theme = get_theme()
    ensure_git()
    active_user = AuthInstance.get_active_user()
    subscription_type = active_user.get("subscription_type", "")
    
    api_key = AuthInstance.api_key
    tokens: dict = AuthInstance.get_active_tokens() or {}

    if use_decoy:
        decoy = DecoyInstance.get_decoy("balance")
        decoy_package_detail = get_package(api_key, tokens, decoy["option_code"])
        if not decoy_package_detail:
            print_panel("Peringatan", "Gagal memuat detail paket decoy")
            pause()
            return False
        
        balance_threshold = decoy_package_detail["package_option"]["price"]
        console.print(f"[{theme['text_warn']}]Pastikan sisa saldo KURANG DARI Rp{balance_threshold}[/]")
        balance_answer = console.input("Apakah ingin melanjutkan pembelian? (y/n): ").strip().lower()
        if balance_answer != "y":
            print_panel("Informasi", "Pembelian dibatalkan")
            pause()
            return None

    family_data = get_family(api_key, tokens, family_code)
    if not family_data:
        print_panel("Peringatan", f"Gagal mengambil data family untuk kode: {family_code}")
        pause()
        return None
    
    family_name = family_data["package_family"]["name"]
    variants = family_data["package_variants"]
    
    console.rule()
    successful_purchases = []
    packages_count = sum(len(v["package_options"]) for v in variants)
    
    purchase_count = 0
    start_buying = start_from_option <= 1

    for variant in variants:
        variant_name = variant["name"]
        for option in variant["package_options"]:
            tokens = AuthInstance.get_active_tokens()
            option_order = option["order"]
            if not start_buying and option_order == start_from_option:
                start_buying = True
            if not start_buying:
                console.print(f"[{theme['text_sub']}]Lewati option {option_order}. {option['name']}[/]")
                continue
            
            option_name = option["name"]
            option_price = option["price"]
            
            purchase_count += 1
            console.print(f"[{theme['text_title']}]Proses pembelian {purchase_count} dari {packages_count}[/]")
            console.print(f"Melanjutkan pembelian: {variant_name} - {option_order}. {option_name} - Rp{option_price}")
            
            payment_items = []
            
            try:
                if use_decoy:                
                    decoy = DecoyInstance.get_decoy("balance")
                    decoy_package_detail = get_package(api_key, tokens, decoy["option_code"])
                    if not decoy_package_detail:
                        print_panel("Peringatan", "Gagal memuat detail paket decoy")
                        pause()
                        return False
                
                target_package_detail = get_package_details(
                    api_key,
                    tokens,
                    family_code,
                    variant["package_variant_code"],
                    option["order"],
                    None,
                    None,
                )
            except Exception as e:
                print_panel("Kesalahan", f"Terjadi error saat mengambil detail paket: {e}")
                console.print(f"Gagal mengambil detail untuk {variant_name} - {option_name}. Dilewati sementara.")
                continue

            payment_items.append(
                PaymentItem(
                    item_code=target_package_detail["package_option"]["package_option_code"],
                    product_type="",
                    item_price=target_package_detail["package_option"]["price"],
                    item_name=f"{randint(1000, 9999)} {target_package_detail['package_option']['name']}",
                    tax=0,
                    token_confirmation=target_package_detail["token_confirmation"],
                )
            )

            if use_decoy:
                payment_items.append(
                    PaymentItem(
                        item_code=decoy_package_detail["package_option"]["package_option_code"],
                        product_type="",
                        item_price=decoy_package_detail["package_option"]["price"],
                        item_name=f"{randint(1000, 9999)} {decoy_package_detail['package_option']['name']}",
                        tax=0,
                        token_confirmation=decoy_package_detail["token_confirmation"],
                    )
                )
            
            overwrite_amount = target_package_detail["package_option"]["price"]
            if use_decoy or overwrite_amount == 0:
                overwrite_amount += decoy_package_detail["package_option"]["price"]
                
            error_msg = ""

            try:
                res = settlement_balance(
                    api_key,
                    tokens,
                    payment_items,
                    "🤑",
                    False,
                    overwrite_amount=overwrite_amount,
                    token_confirmation_idx=1
                )
                
                if res and res.get("status", "") != "SUCCESS":
                    error_msg = res.get("message", "")
                    if "Bizz-err.Amount.Total" in error_msg:
                        error_msg_arr = error_msg.split("=")
                        valid_amount = int(error_msg_arr[1].strip())
                        print_panel("Informasi", f"Total amount disesuaikan menjadi: {valid_amount}")
                        res = settlement_balance(
                            api_key,
                            tokens,
                            payment_items,
                            "SHARE_PACKAGE",
                            False,
                            overwrite_amount=valid_amount,
                            token_confirmation_idx=-1
                        )
                        if res and res.get("status", "") == "SUCCESS":
                            error_msg = ""
                            successful_purchases.append(f"{variant_name}|{option_order}. {option_name} - Rp{option_price}")
                            print_panel("Sukses", "Pembelian berhasil")
                            if pause_on_success:
                                pause()
                        else:
                            error_msg = res.get("message", "")
                else:
                    successful_purchases.append(f"{variant_name}|{option_order}. {option_name} - Rp{option_price}")
                    print_panel("Sukses", "Pembelian berhasil")
                    if pause_on_success:
                        pause()

            except Exception as e:
                print_panel("Kesalahan", f"Terjadi error saat membuat order: {e}")
            
            console.rule()
            should_delay = error_msg == "" or "Failed call ipaas purchase" in error_msg
            if delay_seconds > 0 and should_delay:
                delay_inline(delay_seconds)

    console.print(f"[{theme['text_title']}]Family: {family_name}[/]")
    console.print(f"Total berhasil: {len(successful_purchases)}")
    if successful_purchases:
        console.rule()
        console.print("Daftar pembelian sukses:")
        for purchase in successful_purchases:
            console.print(f"- {purchase}")
    console.rule()
    pause()


def purchase_n_times(
    n: int,
    family_code: str,
    variant_code: str,
    option_order: int,
    use_decoy: bool,
    delay_seconds: int = 0,
    pause_on_success: bool = False,
    token_confirmation_idx: int = 0,
):
    theme = get_theme()
    ensure_git()
    active_user = AuthInstance.get_active_user()
    subscription_type = active_user.get("subscription_type", "")
    
    api_key = AuthInstance.api_key
    tokens: dict = AuthInstance.get_active_tokens() or {}

    if use_decoy:
        decoy = DecoyInstance.get_decoy("balance")
        decoy_package_detail = get_package(api_key, tokens, decoy["option_code"])
        if not decoy_package_detail:
            print_panel("Peringatan", "Gagal memuat detail paket decoy")
            pause()
            return False
        
        balance_threshold = decoy_package_detail["package_option"]["price"]
        console.print(f"[{theme['text_warn']}]Pastikan sisa saldo KURANG DARI Rp{balance_threshold}[/]")
        balance_answer = console.input("Apakah ingin melanjutkan pembelian? (y/n): ").strip().lower()
        if balance_answer != "y":
            print_panel("Informasi", "Pembelian dibatalkan")
            pause()
            return None

    family_data = get_family(api_key, tokens, family_code)
    if not family_data:
        print_panel("Peringatan", f"Gagal mengambil data family untuk kode: {family_code}")
        pause()
        return None
    
    family_name = family_data["package_family"]["name"]
    variants = family_data["package_variants"]
    target_variant = next((v for v in variants if v["package_variant_code"] == variant_code), None)
    if not target_variant:
        print_panel("Peringatan", f"Variant code {variant_code} tidak ditemukan pada family {family_name}")
        pause()
        return None
    
    target_option = next((o for o in target_variant["package_options"] if o["order"] == option_order), None)
    if not target_option:
        print_panel("Peringatan", f"Option order {option_order} tidak ditemukan pada variant {target_variant['name']}")
        pause()
        return None
    
    option_name = target_option["name"]
    option_price = target_option["price"]
    console.rule()
    successful_purchases = []
    
    for i in range(n):
        console.print(f"[{theme['text_title']}]Proses pembelian {i + 1} dari {n}[/]")
        console.print(f"Melanjutkan pembelian: {target_variant['name']} - {option_order}. {option_name} - Rp{option_price}")
        
        api_key = AuthInstance.api_key
        tokens: dict = AuthInstance.get_active_tokens() or {}
        payment_items = []
        
        try:
            if use_decoy:
                decoy = DecoyInstance.get_decoy("balance")
                decoy_package_detail = get_package(api_key, tokens, decoy["option_code"])
                if not decoy_package_detail:
                    print_panel("Peringatan", "Gagal memuat detail paket decoy")
                    pause()
                    return False
            
            target_package_detail = get_package_details(
                api_key,
                tokens,
                family_code,
                target_variant["package_variant_code"],
                target_option["order"],
                None,
                None,
            )
        except Exception as e:
            print_panel("Kesalahan", f"Terjadi error saat mengambil detail paket: {e}")
            console.print(f"Gagal mengambil detail untuk {target_variant['name']} - {option_name}. Dilewati sementara.")
            continue

        payment_items.append(
            PaymentItem(
                item_code=target_package_detail["package_option"]["package_option_code"],
                product_type="",
                item_price=target_package_detail["package_option"]["price"],
                item_name=f"{randint(1000, 9999)} {target_package_detail['package_option']['name']}",
                tax=0,
                token_confirmation=target_package_detail["token_confirmation"],
            )
        )

        if use_decoy:
            payment_items.append(
                PaymentItem(
                    item_code=decoy_package_detail["package_option"]["package_option_code"],
                    product_type="",
                    item_price=decoy_package_detail["package_option"]["price"],
                    item_name=f"{randint(1000, 9999)} {decoy_package_detail['package_option']['name']}",
                    tax=0,
                    token_confirmation=decoy_package_detail["token_confirmation"],
                )
            )
        
        overwrite_amount = target_package_detail["package_option"]["price"]
        if use_decoy:
            overwrite_amount += decoy_package_detail["package_option"]["price"]

        try:
            res = settlement_balance(
                api_key,
                tokens,
                payment_items,
                "🤫",
                False,
                overwrite_amount=overwrite_amount,
                token_confirmation_idx=token_confirmation_idx
            )
            
            if res and res.get("status", "") != "SUCCESS":
                error_msg = res.get("message", "Unknown error")
                if "Bizz-err.Amount.Total" in error_msg:
                    error_msg_arr = error_msg.split("=")
                    valid_amount = int(error_msg_arr[1].strip())
                    print_panel("Informasi", f"Total amount disesuaikan menjadi: {valid_amount}")
                    res = settlement_balance(
                        api_key,
                        tokens,
                        payment_items,
                        "🤫",
                        False,
                        overwrite_amount=valid_amount,
                        token_confirmation_idx=token_confirmation_idx
                    )
                    if res and res.get("status", "") == "SUCCESS":
                        successful_purchases.append(f"{target_variant['name']}|{option_order}. {option_name} - Rp{option_price}")
                        print_panel("Sukses", "Pembelian berhasil")
                        if pause_on_success:
                            pause()
            else:
                successful_purchases.append(f"{target_variant['name']}|{option_order}. {option_name} - Rp{option_price}")
                print_panel("Sukses", "Pembelian berhasil")
                if pause_on_success:
                    pause()
        except Exception as e:
            print_panel("Kesalahan", f"Terjadi error saat membuat order: {e}")
        
        console.rule()

        if delay_seconds > 0 and i < n - 1:
            delay_inline(delay_seconds)

    console.print(f"[{theme['text_title']}]Total pembelian sukses {len(successful_purchases)}/{n}[/]")
    console.print(f"Family: {family_name}\nVariant: {target_variant['name']}\nOption: {option_order}. {option_name} - Rp{option_price}")
    if successful_purchases:
        console.rule()
        console.print("Daftar pembelian sukses:")
        for idx, purchase in enumerate(successful_purchases, start=1):
            console.print(f"{idx}. {purchase}")
    console.rule()
    pause()
    return True


def purchase_n_times_by_option_code(
    n: int,
    option_code: str,
    use_decoy: bool,
    delay_seconds: int = 0,
    pause_on_success: bool = False,
    token_confirmation_idx: int = 0,
):
    theme = get_theme()
    ensure_git()
    active_user = AuthInstance.get_active_user()
    subscription_type = active_user.get("subscription_type", "")
    
    api_key = AuthInstance.api_key
    tokens: dict = AuthInstance.get_active_tokens() or {}

    if use_decoy:
        decoy = DecoyInstance.get_decoy("balance")
        decoy_package_detail = get_package(api_key, tokens, decoy["option_code"])
        if not decoy_package_detail:
            print_panel("Peringatan", "Gagal memuat detail paket decoy")
            pause()
            return False
        
        balance_threshold = decoy_package_detail["package_option"]["price"]
        console.print(f"[{theme['text_warn']}]Pastikan sisa saldo KURANG DARI Rp{balance_threshold}[/]")
        balance_answer = console.input("Apakah ingin melanjutkan pembelian? (y/n): ").strip().lower()
        if balance_answer != "y":
            print_panel("Informasi", "Pembelian dibatalkan")
            pause()
            return None
    
    console.rule()
    successful_purchases = []
    
    for i in range(n):
        console.print(f"[{theme['text_title']}]Proses pembelian {i + 1} dari {n}[/]")
        
        api_key = AuthInstance.api_key
        tokens: dict = AuthInstance.get_active_tokens() or {}
        payment_items = []
        
        try:
            if use_decoy:
                decoy = DecoyInstance.get_decoy("balance")
                decoy_package_detail = get_package(api_key, tokens, decoy["option_code"])
                if not decoy_package_detail:
                    print_panel("Peringatan", "Gagal memuat detail paket decoy")
                    pause()
                    return False
            
            target_package_detail = get_package(api_key, tokens, option_code)
        except Exception as e:
            print_panel("Kesalahan", f"Terjadi error saat mengambil detail paket: {e}")
            continue

        payment_items.append(
            PaymentItem(
                item_code=target_package_detail["package_option"]["package_option_code"],
                product_type="",
                item_price=target_package_detail["package_option"]["price"],
                item_name=f"{randint(1000, 9999)} {target_package_detail['package_option']['name']}",
                tax=0,
                token_confirmation=target_package_detail["token_confirmation"],
            )
        )

        if use_decoy:
            payment_items.append(
                PaymentItem(
                    item_code=decoy_package_detail["package_option"]["package_option_code"],
                    product_type="",
                    item_price=decoy_package_detail["package_option"]["price"],
                    item_name=f"{randint(1000, 9999)} {decoy_package_detail['package_option']['name']}",
                    tax=0,
                    token_confirmation=decoy_package_detail["token_confirmation"],
                )
            )
        
        overwrite_amount = target_package_detail["package_option"]["price"]
        if use_decoy:
            overwrite_amount += decoy_package_detail["package_option"]["price"]

        try:
            res = settlement_balance(
                api_key,
                tokens,
                payment_items,
                "🤫",
                False,
                overwrite_amount=overwrite_amount,
                token_confirmation_idx=token_confirmation_idx
            )
            
            if res and res.get("status", "") != "SUCCESS":
                error_msg = res.get("message", "Unknown error")
                if "Bizz-err.Amount.Total" in error_msg:
                    error_msg_arr = error_msg.split("=")
                    valid_amount = int(error_msg_arr[1].strip())
                    print_panel("Informasi", f"Total amount disesuaikan menjadi: {valid_amount}")
                    res = settlement_balance(
                        api_key,
                        tokens,
                        payment_items,
                        "🤫",
                        False,
                        overwrite_amount=valid_amount,
                        token_confirmation_idx=token_confirmation_idx
                    )
                    if res and res.get("status", "") == "SUCCESS":
                        successful_purchases.append(f"Purchase {i + 1}")
                        print_panel("Sukses", "Pembelian berhasil")
                        if pause_on_success:
                            pause()
            else:
                successful_purchases.append(f"Purchase {i + 1}")
                print_panel("Sukses", "Pembelian berhasil")
                if pause_on_success:
                    pause()
        except Exception as e:
            print_panel("Kesalahan", f"Terjadi error saat membuat order: {e}")
        
        console.rule()

        if delay_seconds > 0 and i < n - 1:
            delay_inline(delay_seconds)

    console.print(f"[{theme['text_title']}]Total pembelian sukses {len(successful_purchases)}/{n}[/]")
    if successful_purchases:
        console.rule()
        console.print("Daftar pembelian sukses:")
        for idx, purchase in enumerate(successful_purchases, start=1):
            console.print(f"{idx}. {purchase}")
    console.rule()
    return True
