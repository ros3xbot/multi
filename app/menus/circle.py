from datetime import datetime
import json
from app.menus.package import get_packages_by_family, show_package_details
from app.menus.util import pause, clear_screen, format_quota_byte
from app.client.circle import (
    get_group_data,
    get_group_members,
    create_circle,
    validate_circle_member,
    invite_circle_member,
    remove_circle_member,
    accept_circle_invitation,
    spending_tracker,
    get_bonus_data,
)
from app.service.auth import AuthInstance
from app.client.encrypt import decrypt_circle_msisdn

WIDTH = 55


def print_header(title: str):
    print("=" * WIDTH)
    print(title.center(WIDTH))
    print("-" * WIDTH)


def show_circle_creation(api_key: str, tokens: dict):
    clear_screen()
    print_header("✨ Bikin Circle Baru")
    parent_name = input("Masukin nama kamu (Parent): ")
    group_name = input("Masukin nama Circle: ")
    member_msisdn = input("Masukin MSISDN member awal (628xxxx): ")
    member_name = input("Masukin nama member awal: ")

    create_res = create_circle(api_key, tokens, parent_name, group_name, member_msisdn, member_name)

    print("📡 Respon server:")
    print(json.dumps(create_res, indent=2))
    pause()


def show_bonus_list(api_key: str, tokens: dict, parent_subs_id: str, family_id: str):
    in_circle_bonus_menu = True
    while in_circle_bonus_menu:
        clear_screen()
        print("🔍 Lagi ambil data bonus...")
        bonus_data = get_bonus_data(api_key, tokens, parent_subs_id, family_id)

        if bonus_data.get("status") != "SUCCESS":
            print("⚠️ Gagal ambil data bonus bro.")
            pause()
            return

        bonus_list = bonus_data.get("data", {}).get("bonuses", [])
        if not bonus_list:
            print("⚠️ Nggak ada bonus tersedia bro.")
            pause()
            return

        print_header("🎁 Circle Bonus List")
        for idx, bonus in enumerate(bonus_list, start=1):
            bonus_name = bonus.get("name", "N/A")
            bonus_type = bonus.get("bonus_type", "N/A")
            action_type = bonus.get("action_type", "N/A")
            action_param = bonus.get("action_param", "N/A")
            print(f"{idx}. {bonus_name} | Type: {bonus_type}")
            print(f"   Action: {action_type} | Param: {action_param}")

        print("-" * WIDTH)
        print("Options:")
        print("00. Balik ke menu utama")
        choice = input("Pilih bonus: ").strip()

        if choice == "00":
            in_circle_bonus_menu = False
        else:
            try:
                bonus_number = int(choice)
                if not (1 <= bonus_number <= len(bonus_list)):
                    print("⚠️ Nomor bonus nggak valid bro.")
                    pause()
                    continue

                selected_bonus = bonus_list[bonus_number - 1]
                action_type = selected_bonus.get("action_type", "N/A")
                action_param = selected_bonus.get("action_param", "N/A")

                if action_type == "PLP":
                    get_packages_by_family(action_param)
                elif action_type == "PDP":
                    show_package_details(api_key, tokens, action_param, False)
                else:
                    print("⚠️ Action type belum ditangani bro.")
                    print(f"Action: {action_type} | Param: {action_param}")
                    pause()
            except ValueError:
                print("⚠️ Input nggak valid bro.")
                pause()


def show_circle_info(api_key: str, tokens: dict):
    in_circle_menu = True
    user: dict = AuthInstance.get_active_user()
    my_msisdn = user.get("number", "")

    while in_circle_menu:
        clear_screen()
        group_res = get_group_data(api_key, tokens)
        if group_res.get("status") != "SUCCESS":
            print("⚠️ Gagal ambil data Circle bro.")
            pause()
            return

        group_data = group_res.get("data", {})
        group_id = group_data.get("group_id", "")

        if group_id == "":
            print("⚠️ Kamu belum join Circle bro.")
            create_new = input("Mau bikin Circle baru? (y/n): ").strip().lower()
            if create_new == "y":
                show_circle_creation(api_key, tokens)
                continue
            else:
                pause()
                return

        if group_data.get("group_status", "N/A") == "BLOCKED":
            print("🚫 Circle ini lagi diblokir bro.")
            pause()
            return

        group_name = group_data.get("group_name", "N/A")
        owner_name = group_data.get("owner_name", "N/A")

        members_res = get_group_members(api_key, tokens, group_id)
        if members_res.get("status") != "SUCCESS":
            print("⚠️ Gagal ambil member Circle bro.")
            pause()
            return

        members = members_res.get("data", {}).get("members", [])
        if not members:
            print("⚠️ Circle ini belum ada member bro.")
            pause()
            return

        parent_member_id, parent_subs_id, parrent_msisdn = "", "", ""
        for member in members:
            if member.get("member_role") == "PARENT":
                parent_member_id = member.get("member_id", "")
                parent_subs_id = member.get("subscriber_number", "")
                parrent_msisdn = decrypt_circle_msisdn(api_key, member.get("msisdn", ""))

        package = members_res.get("data", {}).get("package", {})
        package_name = package.get("name", "N/A")
        benefit = package.get("benefit", {})
        formatted_allocation = format_quota_byte(benefit.get("allocation", 0))
        formatted_remaining = format_quota_byte(benefit.get("remaining", 0))

        spending_res = spending_tracker(api_key, tokens, parent_subs_id, group_id)
        if spending_res.get("status") != "SUCCESS":
            print("⚠️ Gagal ambil spending tracker bro.")
            pause()
            return

        spending_data = spending_res.get("data", {})
        spend = spending_data.get("spend", 0)
        target = spending_data.get("target", 0)

        clear_screen()
        print_header(f"🔄 Circle: {group_name}")
        print(f"Owner: {owner_name} {parrent_msisdn}".center(WIDTH))
        print("-" * WIDTH)
        print(f"Package: {package_name} | {formatted_remaining} / {formatted_allocation}".center(WIDTH))
        print(f"Spending: Rp{spend:,} / Rp{target:,}".center(WIDTH))
        print("=" * WIDTH)

        print("👥 Members:")
        for idx, member in enumerate(members, start=1):
            msisdn = decrypt_circle_msisdn(api_key, member.get("msisdn", "")) or "<No Number>"
            me_mark = "(You)" if str(msisdn) == str(my_msisdn) else ""
            member_type = "Parent" if member.get("member_role") == "PARENT" else "Member"
            join_date = datetime.fromtimestamp(member.get("join_date", 0)).strftime("%Y-%m-%d")
            alloc = format_quota_byte(member.get("allocation", 0))
            used = format_quota_byte(member.get("allocation", 0) - member.get("remaining", 0))

            print(f"{idx}. {msisdn} ({member.get('member_name', 'N/A')}) | {member_type} {me_mark}")
            print(f"   Joined: {join_date} | Slot: {member.get('slot_type', 'N/A')} | Status: {member.get('status', 'N/A')}")
            print(f"   Usage: {used} / {alloc}")
            print("-" * WIDTH)

        print("Options:")
        print("1. Invite Member 👤")
        print("del <number> - Hapus Member ❌")
        print("acc <number> - Accept Invitation ✅")
        print("2. Lihat Bonus 🎁")
        print("00. Balik ke menu utama")
        print("-" * WIDTH)
        choice = input("Pilih opsi: ").strip()

        if choice == "00":
            in_circle_menu = False
        elif choice == "1":
            msisdn_to_invite = input("Masukin MSISDN member (628xxxx): ").strip()

            if not msisdn_to_invite.startswith("628") or not msisdn_to_invite.isdigit() or len(msisdn_to_invite) < 10 or len(msisdn_to_invite) > 14:
                print("⚠️ Nomor nggak valid bro. Pastikan diawali '628' dan panjangnya masuk akal.")
                pause()
                continue

            validate_res = validate_circle_member(api_key, tokens, msisdn_to_invite)
            if validate_res.get("status") == "SUCCESS":
                if validate_res.get("data", {}).get("response_code", "") != "200-2001":
                    print(f"⚠️ Nggak bisa invite {msisdn_to_invite}: {validate_res.get('data', {}).get('message', 'Unknown error')}")
                    pause()
                    continue
            else:
                print("⚠️ Gagal validasi member bro.")
                pause()
                continue

            member_name = input("Masukin nama member: ").strip()
            if not member_name:
                print("⚠️ Nama member nggak boleh kosong bro.")
                pause()
                continue

            invite_res = invite_circle_member(
                api_key,
                tokens,
                msisdn_to_invite,
                member_name,
                group_id,
                parent_member_id
            )

            if invite_res.get("status") == "SUCCESS":
                if invite_res.get("data", {}).get("response_code", "") == "200-00":
                    print(f"✅ Undangan buat {msisdn_to_invite} berhasil dikirim bro.")
                else:
                    print(f"⚠️ Invite gagal: {invite_res.get('data', {}).get('message', 'Unknown error')}")
            else:
                print("💥 Error pas kirim undangan bro.")
                print(json.dumps(invite_res, indent=2))

            pause()

        elif choice.startswith("del "):
            try:
                member_number = int(choice.split(" ")[1])
                if not (1 <= member_number <= len(members)):
                    print("⚠️ Nomor member nggak valid bro.")
                    pause()
                    continue

                member_to_remove = members[member_number - 1]

                if member_to_remove.get("member_role") == "PARENT":
                    print("🚫 Nggak bisa hapus parent bro.")
                    pause()
                    continue

                is_last_member = len(members) == 2
                if is_last_member:
                    print("🚫 Nggak bisa hapus member terakhir bro.")
                    pause()
                    continue

                msisdn_to_remove = decrypt_circle_msisdn(api_key, member_to_remove.get("msisdn", ""))
                confirm = input(f"Yakin mau hapus {msisdn_to_remove} dari Circle? (y/n): ").strip().lower()
                if confirm != "y":
                    print("↩️ Penghapusan dibatalin bro.")
                    pause()
                    continue

                remove_res = remove_circle_member(
                    api_key,
                    tokens,
                    member_to_remove.get("member_id", ""),
                    group_id,
                    parent_member_id,
                    is_last_member
                )
                if remove_res.get("status") == "SUCCESS":
                    print(f"🗑️ {msisdn_to_remove} berhasil dihapus dari Circle.")
                    print(json.dumps(remove_res, indent=2))
                else:
                    print(f"💥 Error: {remove_res}")
            except ValueError:
                print("⚠️ Format input hapus nggak valid bro.")
            pause()

        elif choice.startswith("acc "):
            try:
                member_number = int(choice.split(" ")[1])
                if not (1 <= member_number <= len(members)):
                    print("⚠️ Nomor member nggak valid bro.")
                    pause()
                    continue

                member_to_accept = members[member_number - 1]
                if member_to_accept.get("status") != "INVITED":
                    print("⚠️ Member ini nggak dalam status invited bro.")
                    pause()
                    continue

                msisdn_to_accept = decrypt_circle_msisdn(api_key, member_to_accept.get("msisdn", ""))
                confirm = input(f"Terima undangan buat {msisdn_to_accept}? (y/n): ").strip().lower()
                if confirm != "y":
                    print("↩️ Accept dibatalin bro.")
                    pause()
                    continue

                accept_res = accept_circle_invitation(api_key, tokens, group_id, member_to_accept.get("member_id", ""))
                if accept_res.get("status") == "SUCCESS":
                    print(f"✅ Undangan untuk {msisdn_to_accept} berhasil diterima bro.")
                    print(json.dumps(accept_res, indent=2))
                else:
                    print(f"💥 Error: {accept_res}")
            except ValueError:
                print("⚠️ Format input accept nggak valid bro.")
            pause()

        elif choice == "2":
            show_bonus_list(api_key, tokens, parent_subs_id, group_id)
