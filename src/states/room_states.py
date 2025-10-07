"""
FSM states for room creation and joining
"""
from aiogram.fsm.state import State, StatesGroup


class RoomCreation(StatesGroup):
    """States for room creation flow"""
    waiting_for_name = State()
    waiting_for_language = State()


class RoomJoining(StatesGroup):
    """States for room joining flow"""
    waiting_for_code = State()
    waiting_for_language = State()
