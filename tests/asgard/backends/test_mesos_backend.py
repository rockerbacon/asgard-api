import os
from asynctest import TestCase, mock, skip
from aioresponses import aioresponses
from tests.utils import get_fixture, add_agent_running_tasks, build_mesos_cluster
from tests.conf import TEST_MESOS_ADDRESS

import asgard.sdk.mesos
from asgard.backends.mesos import MesosBackend
import asgard.backends


class MesosBackendTest(TestCase):
    async def setUp(self):
        self.mesos_address = "http://10.0.0.1:5050"
        self.mesos_leader_ip_pactcher = mock.patch(
            "asgard.sdk.mesos.leader_address",
            mock.CoroutineMock(return_value=TEST_MESOS_ADDRESS),
        )
        self.mesos_leader_ip_pactcher.start()

        self.mesos_backend = MesosBackend()

    async def tearDown(self):
        mock.patch.stopall()

    async def test_get_agents_filtered_by_namespace(self):
        with aioresponses(passthrough=["http://127.0.0.1"]) as rsps:
            build_mesos_cluster(
                rsps,
                "ead07ffb-5a61-42c9-9386-21b680597e6c-S10",
                "ead07ffb-5a61-42c9-9386-21b680597e6c-S11",
                "ead07ffb-5a61-42c9-9386-21b680597e6c-S12",
                "ead07ffb-5a61-42c9-9386-21b680597e6c-S9",
            )

            agents = await self.mesos_backend.get_agents(namespace="asgard")
            self.assertEqual(4, len(agents))
            self.assertEqual(
                set(["asgard"]), set([agent.attributes["owner"] for agent in agents])
            )
            self.assertEqual("ead07ffb-5a61-42c9-9386-21b680597e6c-S10", agents[0].id)
            self.assertEqual(2, agents[0].total_apps)

            self.assertEqual("ead07ffb-5a61-42c9-9386-21b680597e6c-S11", agents[1].id)
            self.assertEqual(0, agents[1].total_apps)

            self.assertEqual("ead07ffb-5a61-42c9-9386-21b680597e6c-S12", agents[2].id)
            self.assertEqual(1, agents[2].total_apps)

            self.assertEqual("ead07ffb-5a61-42c9-9386-21b680597e6c-S9", agents[3].id)
            self.assertEqual(1, agents[3].total_apps)

    async def test_get_agents_remove_unused_fields(self):
        with aioresponses(passthrough=["http://127.0.0.1"]) as rsps:
            build_mesos_cluster(rsps, "ead07ffb-5a61-42c9-9386-21b680597e6c-S9")
            agents = await self.mesos_backend.get_agents(namespace="asgard")
            self.assertEqual(1, len(agents))
            self.assertEqual("asgard", agents[0].attributes["owner"])

    async def test_get_agent_by_id_includes_app_count(self):
        agent_id = "ead07ffb-5a61-42c9-9386-21b680597e6c-S10"
        with aioresponses(passthrough=["http://127.0.0.1"]) as rsps:
            build_mesos_cluster(rsps, agent_id)
            agent = await self.mesos_backend.get_agent_by_id(
                namespace="asgard", agent_id=agent_id
            )
            self.assertEqual(agent_id, agent.id)
            self.assertEqual(2, agent.total_apps)

    async def test_get_agent_by_id_returns_None_for_agent_in_another_namespace(self):
        slave_id = "ead07ffb-5a61-42c9-9386-21b680597e6c-S0"
        with aioresponses(passthrough=["http://127.0.0.1"]) as rsps:
            rsps.get(
                f"{self.mesos_address}/redirect",
                status=301,
                headers={"Location": self.mesos_address},
            )
            rsps.get(
                f"{self.mesos_address}/slaves?slave_id={slave_id}",
                payload=get_fixture("agents_multi_owner.json"),
                status=200,
            )
            agent = await self.mesos_backend.get_agent_by_id(
                namespace="dev", agent_id=slave_id  # Agent from asgard-infra namespace
            )
            self.assertIsNone(agent)

    async def test_get_agent_by_id_return_None_if_agent_not_found(self):
        slave_id = "39e1a8e3-0fd1-4ba6-981d-e01318944957-S2"
        with aioresponses(passthrough=["http://127.0.0.1"]) as rsps:
            rsps.get(
                f"{self.mesos_address}/redirect",
                status=301,
                headers={"Location": self.mesos_address},
            )
            rsps.get(
                f"{self.mesos_address}/slaves?slave_id={slave_id}",
                payload={"slaves": []},
                status=200,
            )
            agent = await self.mesos_backend.get_agent_by_id(
                namespace="dev", agent_id=slave_id  # Agent from asgard-infra namespace
            )
            self.assertIsNone(agent)

    async def test_get_apps_returns_empty_list_if_agent_not_found(self):
        slave_id = "39e1a8e3-0fd1-4ba6-981d-e01318944957-S2"
        with aioresponses(passthrough=["http://127.0.0.1"]) as rsps:
            rsps.get(
                f"{self.mesos_address}/redirect",
                status=301,
                headers={"Location": self.mesos_address},
            )
            rsps.get(
                f"{self.mesos_address}/slaves?slave_id={slave_id}",
                payload={"slaves": []},
                status=200,
            )
            apps = await self.mesos_backend.get_apps(namespace="dev", agent_id=slave_id)
            self.assertEqual(0, len(apps))

    async def test_get_apps_returns_empty_list_if_no_apps_running_on_agent(self):
        slave_fixture = get_fixture("agents_multi_owner.json")
        slave = slave_fixture["slaves"][0]
        slave_id = slave["id"]
        slave_address = f"http://{slave['hostname']}:{slave['port']}"
        slave_namespace = slave["attributes"]["owner"]
        with aioresponses(passthrough=["http://127.0.0.1"]) as rsps:
            rsps.get(
                f"{self.mesos_address}/redirect",
                status=301,
                headers={"Location": self.mesos_address},
            )
            rsps.get(
                f"{self.mesos_address}/slaves?slave_id={slave_id}",
                payload=slave_fixture,
                status=200,
            )
            rsps.get(f"{slave_address}/containers", payload=[], status=200)
            apps = await self.mesos_backend.get_apps(
                namespace=slave_namespace, agent_id=slave_id
            )
            self.assertEqual(0, len(apps))

    async def test_get_apps_returns_apps_running_on_agent(self):
        agent_id = "ead07ffb-5a61-42c9-9386-21b680597e6c-S0"
        slave = get_fixture(f"agents/{agent_id}/info.json")
        slave_id = slave["id"]
        slave_address = f"http://{slave['hostname']}:{slave['port']}"
        slave_namespace = slave["attributes"]["owner"]
        with aioresponses(passthrough=["http://127.0.0.1"]) as rsps:
            build_mesos_cluster(rsps, agent_id)
            apps = await self.mesos_backend.get_apps(
                namespace=slave_namespace, agent_id=slave_id
            )
            self.assertEqual(5, len(apps))

            expected_app_ids = sorted(
                [
                    "captura/wetl/visitcentral",
                    "portal/api",
                    "captura/kirby/feeder",
                    "infra/asgard/api",
                    "infra/rabbitmq",
                ]
            )
            self.assertEqual(expected_app_ids, sorted([app.id for app in apps]))
