from asyncworker import App

from asgard.workers.autoscaler.asgard_cloudinterface import AsgardInterface
from asgard.workers.autoscaler.periodicstatechecker import PeriodicStateChecker
from asgard.workers.autoscaler.simple_decision_component import (
    DecisionComponent,
)
from hollowman.log import logger

app = App()


@app.run_every(60 * 5)
async def scale_all_apps(app: App):
    cloud_interface = AsgardInterface()
    state_checker = PeriodicStateChecker(cloud_interface)
    decision_maker = DecisionComponent()

    logger.debug({"AUTOSCALER": "iniciando autoscaler"})
    apps_stats = await state_checker.get_scalable_apps_stats()
    logger.debug({"AUTOSCALER_FETCH_APPS": [app.id for app in apps_stats]})
    scaling_decisions = decision_maker.decide_scaling_actions(apps_stats)
    await cloud_interface.apply_decisions(scaling_decisions)
