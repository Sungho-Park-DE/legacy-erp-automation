"""The wiring object the syncs share: concept instances, adapters and an event log."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app import adapters
from app.adapters.ports import Catalog, ErpRecipe, ErpViewer, PhoneLog, ScreenText
from app.modules.actionpolicy_v1 import ActionPolicy
from app.modules.call_v1 import Calls
from app.modules.jobqueue_v1 import JobQueue
from app.modules.quote_v1 import Quotes
from app.modules.sighting_v1 import Sighting
from app.modules.savejournal_v1 import SaveJournal
from app.modules.verification_v1 import Verification
from app.modules.verification_v2 import Verification as VerificationV2

POLICY_PATH = Path(__file__).resolve().parents[1] / "data" / "policy.json"


@dataclass(frozen=True)
class Event:
    sync: str
    what: str
    data: dict = field(default_factory=dict)


@dataclass
class World:
    calls: Calls
    sighting: Sighting
    quotes: Quotes
    queue: JobQueue
    policy: ActionPolicy
    verification: Verification
    verification_v2: VerificationV2
    journal: SaveJournal
    erp: ErpViewer
    recipe: ErpRecipe
    catalog: Catalog
    phone: PhoneLog
    screen: ScreenText
    log: list[Event] = field(default_factory=list)

    def emit(self, sync: str, what: str, **data) -> None:
        self.log.append(Event(sync, what, data))


def build_world(
    *,
    erp: ErpViewer | None = None,
    recipe: ErpRecipe | None = None,
    catalog: Catalog | None = None,
    phone: PhoneLog | None = None,
    screen: ScreenText | None = None,
    rules: dict | None = None,
    queue: JobQueue | None = None,
    journal: SaveJournal | None = None,
) -> World:
    """`queue` and `journal` can be passed in to stand for state that survives a worker restart."""
    policy = ActionPolicy()
    policy.load(rules if rules is not None else json.loads(POLICY_PATH.read_text(encoding="utf-8")))
    return World(
        calls=Calls(),
        sighting=Sighting(),
        quotes=Quotes(),
        queue=queue if queue is not None else JobQueue(),
        policy=policy,
        verification=Verification(),
        verification_v2=VerificationV2(),
        journal=journal if journal is not None else SaveJournal(),
        erp=erp if erp is not None else adapters.make_erp(),
        recipe=recipe if recipe is not None else adapters.make_recipe(),
        catalog=catalog if catalog is not None else adapters.make_catalog(),
        phone=phone if phone is not None else adapters.make_phone(),
        screen=screen if screen is not None else adapters.make_screen(),
    )
