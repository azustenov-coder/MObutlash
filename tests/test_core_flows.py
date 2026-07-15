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


if __name__ == "__main__":
    unittest.main()
