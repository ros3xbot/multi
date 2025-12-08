from app2.client.store.redeemables import get_redeemables
from app.service.auth import AuthInstance
from app2.menus.util import clear_screen, pause, print_panel, simple_number, delay_inline
from app2.menus.package import show_package_details, get_packages_by_family
from app2.config.imports import *
from datetime import datetime

console = Console()


def show_redeemables_menu(is_enterprise: bool = False):
    """Menampilkan menu redeemables (bonus/reward) yang tersedia."""
    theme = get_theme()
    in_redeemables_menu = True
    while in_redeemables_menu:
        api_key = AuthInstance.api_key
        tokens = AuthInstance.get_active_tokens()
        
        redeemables_res = get_redeemables(api_key, tokens, is_enterprise)
        if not redeemables_res:
            print_panel("Informasi", "Tidak ada redeemables tersedia.")
            in_redeemables_menu = False
            continue
        
        categories = redeemables_res.get("data", {}).get("categories", [])
        clear_screen()
        ensure_git()
        
        console.print(Panel(
            Align.center("Redeemables", vertical="middle"),
            border_style=theme["border_info"],
            padding=(1, 2),
            expand=True
        ))
        simple_number()
        
        packages = {}
        for i, category in enumerate(categories):
            category_name = category.get("category_name", "N/A")
            category_code = category.get("category_code", "N/A")
            redeemables = category.get("redeemables", [])
            
            letter = chr(65 + i)
            table = Table(box=MINIMAL_DOUBLE_HEAD, expand=True)
            table.add_column("Kode", style=theme["text_key"], width=6)
            table.add_column("Nama Barang", style=theme["text_body"])
            table.add_column("Berlaku", style=theme["text_date"])
            table.add_column("Tipe", style=theme["text_body"])
            
            if not redeemables:
                table.add_row("-", f"{category_name} (kosong)", "-", "-")
            else:
                for j, redeemable in enumerate(redeemables):
                    name = redeemable.get("name", "N/A")
                    valid_until = redeemable.get("valid_until", 0)
                    valid_until_date = datetime.fromtimestamp(valid_until).strftime("%Y-%m-%d")
                    action_param = redeemable.get("action_param", "")
                    action_type = redeemable.get("action_type", "")
                    
                    code = f"{letter}{j+1}"
                    packages[code.lower()] = {
                        "action_param": action_param,
                        "action_type": action_type
                    }
                    table.add_row(code, name, valid_until_date, action_type)
            
            console.print(Panel(
                table,
                title=f"[{theme['text_title']}]Kategori: {category_name}[/] (Kode: {category_code})",
                border_style=theme["border_info"],
                padding=(0, 0),
                expand=True
            ))
        
        nav = Table(show_header=False, box=MINIMAL_DOUBLE_HEAD, expand=True)
        nav.add_column(justify="right", style=theme["text_key"], width=6)
        nav.add_column(style=theme["text_body"])
        nav.add_row("00", f"[{theme['text_sub']}]Kembali ke menu utama[/]")
        nav.add_row("99", "Redeem semua bonus")  # tambahan menu baru
        
        console.print(Panel(nav, border_style=theme["border_primary"], expand=True))
        
        choice = console.input(f"[{theme['text_sub']}]Pilih redeemable (misal A1, B2, 99):[/{theme['text_sub']}] ").strip()
        if choice == "00":
            in_redeemables_menu = False
            continue

        if choice == "99":
            show_redeem_all_bonuses(api_key, tokens, categories)
            pause()
            continue
        
        selected_pkg = packages.get(choice.lower())
        if not selected_pkg:
            print_panel("Kesalahan", "Pilihan tidak valid.")
            pause()
            continue
        
        action_param = selected_pkg["action_param"]
        action_type = selected_pkg["action_type"]
        
        if action_type == "PLP":
            get_packages_by_family(action_param, is_enterprise, "")
        elif action_type == "PDP":
            show_package_details(api_key, tokens, action_param, is_enterprise)
        else:
            print_panel("Informasi", f"Tidak ada aksi untuk tipe ini: {action_type}\nParam: {action_param}")
            pause()


def show_redeem_all_bonuses(api_key, tokens, categories):
    """Redeem semua bonus bertipe PDP dengan payment_for=REDEEM_VOUCHER."""
    theme = get_theme()
    clear_screen()

    console.print(Panel(
        Align.center("Redeem Semua Bonus", vertical="middle"),
        border_style=theme["border_info"],
        padding=(1, 2),
        expand=True
    ))
    simple_number()
    ensure_git()

    candidates = []
    for category in categories:
        for r in category.get("redeemables", []):
            if r.get("action_type") == "PDP":
                option_code = r.get("action_param")
                pkg = get_package(api_key, tokens, option_code)
                if not pkg:
                    continue
                family = pkg.get("package_family", {}) or {}
                if (family.get("payment_for") or "BUY_PACKAGE") == "REDEEM_VOUCHER":
                    option = pkg.get("package_option", {}) or {}
                    variant = pkg.get("package_detail_variant", {}) or {}
                    candidates.append({
                        "option_code": option_code,
                        "token_confirmation": pkg.get("token_confirmation", ""),
                        "ts_to_sign": pkg.get("timestamp", ""),
                        "price": option.get("price", 0),
                        "item_name": variant.get("name", "") or option.get("name", ""),
                        "title": f"{family.get('name','')} - {variant.get('name','')} - {option.get('name','')}".strip()
                    })

    if not candidates:
        print_panel("Informasi", "Tidak ada bonus yang dapat diredeem.")
        return

    preview = Table(box=MINIMAL_DOUBLE_HEAD, expand=True)
    preview.add_column("No", style=theme["text_key"], width=4, justify="right")
    preview.add_column("Kode Opsi", style=theme["text_body"])
    preview.add_column("Nama", style=theme["text_body"])
    preview.add_column("Harga", style=theme["text_money"], justify="right")
    for idx, c in enumerate(candidates, start=1):
        preview.add_row(str(idx), c["option_code"], c["title"], f"Rp {get_rupiah(c['price'])}")

    console.print(Panel(
        preview,
        title=f"[{theme['text_title']}]Daftar bonus yang akan diredeem[/]",
        border_style=theme["border_success"],
        padding=(0, 0),
        expand=True
    ))

    confirm = console.input("Lanjutkan redeem semua bonus? (y/n): ").strip().lower()
    if confirm != 'y':
        print_panel("Informasi", "Proses dibatalkan.")
        return

    delay_seconds = 10 * 60  # default 10 menit

    results_table = Table(box=MINIMAL_DOUBLE_HEAD, expand=True)
    results_table.add_column("No", style=theme["text_key"], width=4, justify="right")
    results_table.add_column("Kode Opsi", style=theme["text_body"])
    results_table.add_column("Status", style=theme["text_body"])
    results_table.add_column("Keterangan", style=theme["text_sub"])

    for idx, c in enumerate(candidates, start=1):
        res = settlement_bounty(
            api_key=api_key,
            tokens=tokens,
            token_confirmation=c["token_confirmation"],
            ts_to_sign=c["ts_to_sign"],
            payment_target=c["option_code"],
            price=c["price"],
            item_name=c["item_name"]
        )

        status = "Berhasil"
        note = "-"
        if isinstance(res, dict):
            if res.get("status") != "SUCCESS":
                status = "Gagal"
                note = res.get("message", "Terjadi kesalahan.")
        results_table.add_row(str(idx), c["option_code"], status, note)

        if idx < len(candidates):
            delay_inline(delay_seconds)

    console.print(Panel(
        results_table,
        title=f"[{theme['text_title']}]Ringkasan hasil redeem[/]",
        border_style=theme["border_primary"],
        padding=(0, 0),
        expand=True
    ))
