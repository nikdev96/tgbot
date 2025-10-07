"""
Room models for translation rooms feature
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict


@dataclass
class Room:
    """Room model"""
    id: int
    code: str
    creator_id: int
    name: Optional[str]
    status: str  # active/closed
    max_members: int
    created_at: datetime
    expires_at: Optional[datetime]

    def is_active(self) -> bool:
        """Check if room is active"""
        return self.status == 'active'

    def is_expired(self) -> bool:
        """Check if room is expired"""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at


@dataclass
class RoomMember:
    """Room member model"""
    room_id: int
    user_id: int
    language_code: str
    role: str  # creator/member
    joined_at: datetime
    user_profile: Dict[str, Optional[str]]  # username, first_name, last_name

    def is_creator(self) -> bool:
        """Check if member is room creator"""
        return self.role == 'creator'

    def display_name(self) -> str:
        """Get display name for member"""
        if self.user_profile.get('username'):
            return f"@{self.user_profile['username']}"
        if self.user_profile.get('first_name'):
            name = self.user_profile['first_name']
            if self.user_profile.get('last_name'):
                name += f" {self.user_profile['last_name']}"
            return name
        return f"User {self.user_id}"


@dataclass
class RoomMessage:
    """Room message model"""
    id: int
    room_id: int
    user_id: int
    message_text: str
    language_code: str
    message_type: str  # text/voice/system
    created_at: datetime


def room_from_dict(data: Dict) -> Room:
    """Create Room from dictionary"""
    return Room(
        id=data['id'],
        code=data['code'],
        creator_id=data['creator_id'],
        name=data.get('name'),
        status=data['status'],
        max_members=data['max_members'],
        created_at=data['created_at'],
        expires_at=data.get('expires_at')
    )


def member_from_dict(data: Dict) -> RoomMember:
    """Create RoomMember from dictionary"""
    return RoomMember(
        room_id=data['room_id'],
        user_id=data['user_id'],
        language_code=data['language_code'],
        role=data['role'],
        joined_at=data['joined_at'],
        user_profile=data['user_profile']
    )
