from typing import List, Dict

import asgard.clients.apps.client as asgard_client
from asgard.workers.autoscaler.cloudinterface import CloudInterface
from asgard.workers.converters.asgard_converter import (
    AppConverter,
    AppStatsConverter,
    DecisionConverter,
)
from asgard.workers.models.decision import Decision
from asgard.workers.models.scalable_app import ScalableApp


class AsgardInterface(CloudInterface):
    async def fetch_all_apps(self) -> List[ScalableApp]:
        app_dtos = await asgard_client.get_all_apps()
        apps = AppConverter.all_to_model(app_dtos)

        return apps

    async def get_all_scalable_apps(self) -> List[ScalableApp]:
        all_apps = await self.fetch_all_apps()
        if all_apps:
            return list(filter(ScalableApp.is_set_to_scale, all_apps))

        return list()

    async def get_app_stats(self, app: ScalableApp) -> ScalableApp:
        app_stats_dto = await asgard_client.get_app_stats(app.id)
        app.app_stats = AppStatsConverter.to_model(app_stats_dto)

        return app

    async def apply_decisions(
        self, scaling_decisions: List[Decision]
    ) -> List[Dict]:
        decision_dtos = DecisionConverter.all_to_dto(scaling_decisions)
        post_body = await asgard_client.post_scaling_decisions(decision_dtos)

        return post_body
