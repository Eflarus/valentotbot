from __future__ import annotations

import secrets
import string
from typing import Sequence

from valentotbot.application.dto import CreateLinkInput
from valentotbot.domain.entities import Link
from valentotbot.domain.interfaces import LinkRepository


class CreateLinkService:
    def __init__(self, link_repo: LinkRepository) -> None:
        self._link_repo = link_repo

    def _generate_slug(self, length: int = 10) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    async def execute(self, input_data: CreateLinkInput) -> Link:
        slug = self._generate_slug()
        while await self._link_repo.exists_slug(slug):
            slug = self._generate_slug()
        return await self._link_repo.create(
            owner_user_id=input_data.owner_user_id,
            slug=slug,
            label=input_data.label,
            prompt=input_data.prompt,
        )


class ListLinksService:
    def __init__(self, link_repo: LinkRepository) -> None:
        self._link_repo = link_repo

    async def execute(self, owner_user_id: int) -> Sequence[Link]:
        return await self._link_repo.list_by_owner(owner_user_id)
