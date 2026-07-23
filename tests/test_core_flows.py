import unittest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.common import EXCEL_REPORT_BUTTONS, get_main_keyboard, get_role_by_input, is_main_menu_text
from handlers.controller import get_approval_target_status
from handlers.mechanic import parse_request_text
from text_utils import cyrillize_telegram_payload, latin_to_cyrillic


class CoreFlowTests(unittest.TestCase):
    def test_every_role_main_menu_button_resets_stale_dialog_state(self):
        roles = ["super_admin", "manager", "observer", "mechanic", "brigadier", "warehouseman", "courier"]
        for role in roles:
            markup = get_main_keyboard(
                role,
                request_counts={},
                leadership_counts={},
                courier_counts={},
            )
            for row in markup.keyboard:
                for button in row:
                    self.assertTrue(is_main_menu_text(button.text), f"{role}: {button.text}")

                    visible_text = latin_to_cyrillic(button.text)
                    self.assertTrue(
                        is_main_menu_text(visible_text),
                        f"{role} (Telegramda ko'rinadigan matn): {visible_text}",
                    )

    def test_excel_button_visible_text_matches_handler_variant(self):
        visible_text = latin_to_cyrillic("Excel ҳисобот юклаб олиш 📊")
        self.assertEqual(visible_text, "Ехсел ҳисобот юклаб олиш 📊")
        self.assertIn(visible_text, EXCEL_REPORT_BUTTONS)

    def test_all_registration_roles_work_after_cyrillization(self):
        expected = {
            "Boshqaruvchi": "manager",
            "Boshqaruvchi 2": "observer",
            "Mexanik": "mechanic",
            "Brigadir RB": "brigadier",
            "Ta'minotchi": "courier",
            "Skladchik": "warehouseman",
        }
        for label, role in expected.items():
            with self.subTest(label=label):
                self.assertEqual(get_role_by_input(latin_to_cyrillic(label)), role)

    def test_every_role_has_a_main_menu(self):
        roles = [
            "super_admin", "manager", "observer", "mechanic",
            "brigadier", "warehouseman", "courier",
        ]
        for role in roles:
            with self.subTest(role=role):
                markup = get_main_keyboard(role)
                self.assertTrue(markup.keyboard)

    def test_mechanic_menu_shows_all_request_counters(self):
        markup = get_main_keyboard(
            "mechanic",
            request_counts={
                "total": 12,
                "unfinished": 5,
                "completed": 7,
                "ready_for_pickup": 2,
            },
        )
        visible = " | ".join(button.text for row in markup.keyboard for button in row)
        for expected in (
            "Менинг заявкаларим 📂 (12)",
            "Тугалланмаган заявкалар ⏳ (5)",
            "Складдан олиш 📦 (2)",
            "Тугалланган заявкалар ✅ (7)",
        ):
            self.assertIn(expected, visible)

    def test_repair_and_purchase_take_different_paths(self):
        self.assertEqual(get_approval_target_status("repair"), "issued_to_mechanic")
        self.assertEqual(get_approval_target_status("purchase"), "approved")

    def test_visible_text_changes_but_callback_data_does_not(self):
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Bekor qilish", callback_data="cancel_action")]]
        )
        converted = cyrillize_telegram_payload(markup)
        button = converted.inline_keyboard[0][0]
        self.assertEqual(button.text, "Бекор қилиш")
        self.assertEqual(button.callback_data, "cancel_action")

    def test_html_and_links_are_preserved(self):
        text = "<b>Skladdan oldim</b> https://example.com"
        self.assertEqual(
            latin_to_cyrillic(text),
            "<b>Складдан олдим</b> https://example.com",
        )


class PerformancePathTests(unittest.IsolatedAsyncioTestCase):
    async def test_simple_request_uses_fast_local_parser(self):
        result = await parse_request_text("2 ta balon")
        self.assertEqual(result, [{"type": "purchase", "name": "balon", "qty": 2}])

    async def test_cyrillic_units_parsing(self):
        result1 = await parse_request_text("balon 2 та")
        self.assertEqual(result1, [{"type": "purchase", "name": "balon", "qty": 2}])
        
        result2 = await parse_request_text("2 та балон")
        self.assertEqual(result2, [{"type": "purchase", "name": "балон", "qty": 2}])

    async def test_multiline_shifting_and_names_with_numbers(self):
        text = (
            "шкварной комплект 1 та\n"
            "ресор кронштейн 2 та\n"
            "ресор 40см 90/16 1 та\n"
            "ресор кронштейн сиргаси 2та\n"
            "ресор палец олди втулка 6 та\n"
            "ПГУга жидкост 1 та\n"
            "тяга тепа past orqaga 6 ta\n"
            "литол 5кг 1 та"
        )
        result = await parse_request_text(text)
        expected = [
            {"type": "purchase", "name": "шкварной комплект", "qty": 1},
            {"type": "purchase", "name": "ресор кронштейн", "qty": 2},
            {"type": "purchase", "name": "ресор 40см 90/16", "qty": 1},
            {"type": "purchase", "name": "ресор кronstein sirgasi", "qty": 2}, # note casing conversion happens, let's just make it exact
        ]
        # Let's verify each item matches perfectly
        self.assertEqual(len(result), 8)
        self.assertEqual(result[0], {"type": "purchase", "name": "шкварной комплект", "qty": 1})
        self.assertEqual(result[1], {"type": "purchase", "name": "ресор кронштейн", "qty": 2})
        self.assertEqual(result[2], {"type": "purchase", "name": "ресор 40см 90/16", "qty": 1})
        self.assertEqual(result[3], {"type": "purchase", "name": "ресор кронштейн сиргаси", "qty": 2})
        self.assertEqual(result[4], {"type": "purchase", "name": "ресор палец олди втулка", "qty": 6})
        self.assertEqual(result[5], {"type": "purchase", "name": "ПГУга жидкост", "qty": 1})
        self.assertEqual(result[6], {"type": "purchase", "name": "тяга тепа past orqaga", "qty": 6})
        self.assertEqual(result[7], {"type": "purchase", "name": "литол 5кг", "qty": 1})

    async def test_smart_vehicle_splitting_and_loaders(self):
        text = (
            "Vozdux filtr 3250.   5 ta 491.499.494.480.492.\n"
            "Pagrushi 3 ga bendeks 1 ta\n"
            "Chakman bendeks 2 ta"
        )
        result = await parse_request_text(text, default_vehicle="491")
        self.assertEqual(len(result), 7)
        
        for i in range(5):
            self.assertEqual(result[i]["name"], "Vozdux filtr 3250")
            self.assertEqual(result[i]["qty"], 1)
            self.assertEqual(result[i]["type"], "purchase")
        self.assertEqual(result[0]["vehicle"], "491")
        self.assertEqual(result[1]["vehicle"], "499")
        self.assertEqual(result[2]["vehicle"], "494")
        self.assertEqual(result[3]["vehicle"], "480")
        self.assertEqual(result[4]["vehicle"], "492")
        
        self.assertEqual(result[5], {"type": "purchase", "name": "bendeks", "qty": 1, "vehicle": "Pagrushi 3"})
        self.assertEqual(result[6], {"type": "purchase", "name": "Chakman bendeks", "qty": 2, "vehicle": "491"})

    def test_bulk_request_manage_keyboard(self):
        from handlers.common import get_bulk_request_manage_keyboard
        markup = get_bulk_request_manage_keyboard(12345)
        self.assertTrue(markup.inline_keyboard)
        row1 = markup.inline_keyboard[0]
        self.assertEqual(row1[0].text, "Ҳаммасини тасдиқлаш ✅")
        self.assertEqual(row1[0].callback_data, "bulk_approve_12345")
        self.assertEqual(row1[1].text, "Ҳаммасини рад etish ❌")
        self.assertEqual(row1[1].callback_data, "bulk_reject_12345")
        
        row2 = markup.inline_keyboard[1]
        self.assertEqual(row2[0].text, "Ҳаммасини қайта ишлашга 🔄")
        self.assertEqual(row2[0].callback_data, "bulk_revision_12345")

        row3 = markup.inline_keyboard[2]
        self.assertEqual(row3[0].callback_data, "hamma_approve_all")

    def test_request_manage_keyboard_has_approve_all(self):
        from handlers.common import get_request_manage_keyboard
        markup = get_request_manage_keyboard(999)
        callbacks = [b.callback_data for row in markup.inline_keyboard for b in row]
        self.assertIn("hamma_approve_all", callbacks)


    def test_courier_menu_has_zayavka_yaratish_button(self):
        markup_dynamic = get_main_keyboard("courier", courier_counts={"available": 1, "searching_items": 0, "active": 2, "awaiting_receipt": 0})
        buttons_dynamic = [b.text for row in markup_dynamic.keyboard for b in row]
        self.assertIn("Zayavka yaratish ✍️", buttons_dynamic)

        markup_static = get_main_keyboard("courier")
        buttons_static = [b.text for row in markup_static.keyboard for b in row]
        self.assertIn("Заявка яратиш ✍️", buttons_static)


if __name__ == "__main__":
    unittest.main()
