import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from handlers.common import get_main_keyboard, get_request_manage_keyboard, get_bulk_request_manage_keyboard
from handlers.assembler import start_courier_request_creation
from handlers.mechanic import RequestCreationStates, process_vehicle_selection, process_veh_newreq
from handlers.controller import approve_all_pending_requests


class NewFeaturesIntegrationTest(unittest.IsolatedAsyncioTestCase):
    
    async def test_courier_main_menu_buttons(self):
        # Dynamic courier menu with counts
        dyn_kb = get_main_keyboard("courier", courier_counts={"available": 3, "searching_items": 1, "active": 2, "awaiting_receipt": 0})
        dyn_texts = [btn.text for row in dyn_kb.keyboard for btn in row]
        self.assertIn("Zayavka yaratish ✍️", dyn_texts)
        
        # Static courier menu
        stat_kb = get_main_keyboard("courier")
        stat_texts = [btn.text for row in stat_kb.keyboard for btn in row]
        self.assertIn("Заявка яратиш ✍️", stat_texts)

    async def test_leadership_keyboards_contain_approve_all(self):
        req_kb = get_request_manage_keyboard(101)
        req_callbacks = [btn.callback_data for row in req_kb.inline_keyboard for btn in row]
        self.assertIn("hamma_approve_all", req_callbacks)

        bulk_kb = get_bulk_request_manage_keyboard(202)
        bulk_callbacks = [btn.callback_data for row in bulk_kb.inline_keyboard for btn in row]
        self.assertIn("hamma_approve_all", bulk_callbacks)

    @patch("database.get_user", new_callable=AsyncMock)
    async def test_courier_start_request_creation_permission(self, mock_get_user):
        mock_get_user.return_value = {"id": 123, "role": "courier", "full_name": "Test Courier"}
        
        message = MagicMock()
        message.from_user.id = 123
        message.answer = AsyncMock()
        
        state = MagicMock(spec=FSMContext)
        state.clear = AsyncMock()
        state.set_state = AsyncMock()
        
        await start_courier_request_creation(message, state)
        
        state.clear.assert_called_once()
        state.set_state.assert_called_once_with(RequestCreationStates.waiting_for_vehicle)
        message.answer.assert_called_once()
        self.assertIn("Заявка яратиш (1/4)", message.answer.call_args[0][0])

    @patch("database.get_user", new_callable=AsyncMock)
    async def test_courier_vehicle_selection_handler(self, mock_get_user):
        mock_get_user.return_value = {"id": 123, "role": "courier", "full_name": "Test Courier"}
        
        message = MagicMock()
        message.from_user.id = 123
        message.text = "Gazan-01"
        message.answer = AsyncMock()
        
        state = MagicMock(spec=FSMContext)
        state.update_data = AsyncMock()
        state.set_state = AsyncMock()
        
        await process_vehicle_selection(message, state)
        
        state.update_data.assert_called_once_with(vehicle_name="Gazan-01", temp_items=[])
        state.set_state.assert_called_once_with(RequestCreationStates.waiting_for_photo)
        message.answer.assert_called_once()

    @patch("database.get_user", new_callable=AsyncMock)
    @patch("database.get_requests_by_status", new_callable=AsyncMock)
    @patch("database.get_users_by_role", new_callable=AsyncMock)
    @patch("database.update_request_status", new_callable=AsyncMock)
    async def test_approve_all_pending_requests(self, mock_update_status, mock_get_users, mock_get_reqs, mock_get_user):
        mock_get_user.return_value = {"id": 999, "role": "manager", "full_name": "Main Manager"}
        mock_get_reqs.side_effect = [
            [{"id": 1, "request_type": "purchase", "created_by": 10, "creator_name": "Mech 1", "description": "Part 1", "created_at": "2026-07-23"}],
            [{"id": 2, "request_type": "repair", "created_by": 11, "creator_name": "Mech 2", "description": "Fix 2", "created_at": "2026-07-23"}]
        ]
        mock_get_users.return_value = []
        
        callback = MagicMock()
        callback.from_user.id = 999
        callback.answer = AsyncMock()
        callback.message = MagicMock()
        callback.message.edit_text = AsyncMock()
        callback.message.photo = None
        
        await approve_all_pending_requests(callback)
        
        self.assertEqual(mock_update_status.call_count, 2)
        callback.answer.assert_called_once()
        self.assertIn("муваффақиятли тасдиқланди", callback.answer.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
