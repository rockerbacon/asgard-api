from http import HTTPStatus

from aiohttp import ClientTimeout
from aiohttp.client_exceptions import ClientResponseError
from aioresponses import aioresponses
from asynctest import TestCase
from asynctest.mock import CoroutineMock, Mock, ANY
from yarl import URL

from asgard.http.client import (
    _HttpClient,
    _HttpClientMaker,
    default_http_client_timeout,
    HttpClient,
)
from asgard.http.exceptions import (
    HTTPNotFound,
    HTTPInternalServerError,
    HTTPBadRequest,
)


class LegacyHttpClientTest(TestCase):
    async def setUp(self):
        self._session_mock = CoroutineMock(
            post=CoroutineMock(),
            put=CoroutineMock(),
            delete=CoroutineMock(),
            get=CoroutineMock(),
            close=CoroutineMock(),
        )
        self.session_class_mock = Mock(return_value=self._session_mock)

    async def test_calls_apropriate_method_on_shared_session(self):
        client = _HttpClient(
            self.session_class_mock, "https://httpbin.org/ip", "POST"
        )
        async with client:
            self.session_class_mock.assert_called_with()
            client._session.post.assert_awaited_with("https://httpbin.org/ip")

    async def test_close_shared_session_on_context_exit(self):
        client = _HttpClient(
            self.session_class_mock, "https://httpbin.org/ip", "POST"
        )
        async with client:
            self.session_class_mock.assert_called_with()
            client._session.close.assert_not_awaited()
        client._session.close.assert_awaited_with()


class HttpClientMkakerTest(TestCase):
    async def setUp(self):
        self._session_mock = CoroutineMock(
            post=CoroutineMock(),
            put=CoroutineMock(),
            delete=CoroutineMock(),
            get=CoroutineMock(),
            close=CoroutineMock(),
        )
        self.session_class_mock = Mock(return_value=self._session_mock)
        self.url = "https://httpbin.org/ip"

    async def test_different_args_kwargs_for_session_and_client_get(self):
        """
        Devemos ter args/kwargs distintos para a ClientSession e para
        o http_client final (get/post/etc)
        Por exemplo: Tanto a SessionClass quanto o client recebem `timeout` com kwargs,
        mas apenas o client recebe `allow_redirects`, por exemplo.

        Atualmente os args/kwargs passados para o client (get/post/etc) estão sendo repassados
        para criar a ClientSession, isso impede de usar o client dessa forma:
            async with http_client.get(URL, allow_redirects=False) as response:
                ...
        """
        client_maker = _HttpClientMaker(
            self.session_class_mock, 10, 30, param1=42, param2=60
        )
        async with client_maker.get(
            self.url, allow_redirects=False
        ) as response:
            self.session_class_mock.assert_called_with(
                10, 30, param1=42, param2=60
            )
            self._session_mock.get.assert_awaited_with(
                self.url, allow_redirects=False
            )

    async def test_different_args_kwargs_for_session_and_client_post(self):
        client_maker = _HttpClientMaker(
            self.session_class_mock, 10, 30, param1=42, param2=60
        )
        async with client_maker.post(
            self.url, allow_redirects=False
        ) as response:
            self.session_class_mock.assert_called_with(
                10, 30, param1=42, param2=60
            )
            self._session_mock.post.assert_awaited_with(
                self.url, allow_redirects=False
            )

    async def test_different_args_kwargs_for_session_and_client_put(self):
        client_maker = _HttpClientMaker(
            self.session_class_mock, 10, 30, param1=42, param2=60
        )
        async with client_maker.put(
            self.url, allow_redirects=False
        ) as response:
            self.session_class_mock.assert_called_with(
                10, 30, param1=42, param2=60
            )
            self._session_mock.put.assert_awaited_with(
                self.url, allow_redirects=False
            )

    async def test_different_args_kwargs_for_session_and_client_delete(self):
        client_maker = _HttpClientMaker(
            self.session_class_mock, 10, 30, param1=42, param2=60
        )
        async with client_maker.delete(
            self.url, allow_redirects=False
        ) as response:
            self.session_class_mock.assert_called_with(
                10, 30, param1=42, param2=60
            )
            self._session_mock.delete.assert_awaited_with(
                self.url, allow_redirects=False
            )

    async def test_uses_default_timeout_configs(self):
        self.assertEqual(default_http_client_timeout.connect, 1)
        self.assertEqual(default_http_client_timeout.total, 30)

    async def test_with_block_on_client_return_session(self):
        session_class = Mock(return_value=self._session_mock)
        client_maker = _HttpClientMaker(session_class)

        async with client_maker as session:
            self.assertEqual(session, self._session_mock)

    async def test_reuse_session(self):
        session_class = Mock(return_value=self._session_mock)
        client_maker = _HttpClientMaker(session_class)

        async with client_maker as session1:
            async with client_maker as session2:
                self.assertEqual(session1, self._session_mock)
                self.assertEqual(session2, self._session_mock)
                session_class.assert_called_once()

    async def test_shared_session_must_be_closed_on_context_exit(self):
        """
        Se não fechamos a sessão, caso o loop seja trocado, o http_client
        que já foi usado antes (e por isso já tem uma session aberta) para
        de funcionar com o erro "loop is closed".

        O que temos que fazer é melhorar a API desse http_client. Idealmente
        exigino que ele seja instanciado antes de ser usado.
        Em vez de fazermos assim:
        from asgard.http.client import http_client

        async with http_client as client:
          await client.get(...)

        Fazer algo nessa linha:
        from asgard.http.client import HttpClient

        client = HttpClient(headers=..., ...)
        await client.get(...)
        """
        client = _HttpClientMaker(self.session_class_mock)
        original_session = None
        async with client:
            self.session_class_mock.assert_called_with(
                timeout=default_http_client_timeout
            )
            client.session.close.assert_not_awaited()
            original_session = client.session
        original_session.close.assert_awaited()
        self.assertIsNone(client.session)

    async def test_call_session_with_default_timeout_settings(self):
        session_class = Mock(return_value=self._session_mock)
        client_maker = _HttpClientMaker(session_class)

        async with client_maker as session:
            pass
        session_class.assert_called_with(timeout=default_http_client_timeout)


TEST_URL = "http://server.com"


class HttpClientTest(TestCase):
    async def setUp(self):
        self.session_mock = CoroutineMock(
            post=CoroutineMock(),
            put=CoroutineMock(),
            delete=CoroutineMock(),
            get=CoroutineMock(),
            close=CoroutineMock(),
            request=CoroutineMock(),
        )
        self.session_class_mock = Mock(return_value=self.session_mock)

    async def test_reuse_session_on_subsequent_requests(self):
        client = HttpClient()
        with aioresponses() as rsps:
            rsps.get(TEST_URL, status=200)
            rsps.get(TEST_URL, status=200)

            await client.get(TEST_URL)

            client_session = client._session

            await client.get(TEST_URL)

            self.assertTrue(client_session is client._session)

    async def test_can_merge_default_headers_with_headers_passed_on_the_request_real_request(
        self
    ):
        """
        O aioresponses não funciona quando usamos default_headers no ClientSession.
        """
        default_headers = {"X-Header": "Value"}
        additional_headers = {"X-More": "Other"}

        client = HttpClient(headers=default_headers)
        resp = await client.get(
            "https://httpbin.org/headers", headers=additional_headers
        )
        self.assertEqual(HTTPStatus.OK, resp.status)

        resp_data = await resp.json()
        self.assertEqual("Value", resp_data["headers"].get("X-Header"))
        self.assertEqual("Other", resp_data["headers"].get("X-More"))

    async def test_headers_passed_on_the_request_ovewrites_default_headers(
        self
    ):
        """
        Se um header passado em `client.get(..., headers={})` tiver o mesmo nome de um
        outro header passado na instanciação do http client, o header do request
        deve ser usado
        """
        default_headers = {"X-Header": "Value"}
        additional_headers = {"X-More": "Other", "X-Header": "Override"}

        client = HttpClient(headers=default_headers)
        with aioresponses() as rsps:
            rsps.get(TEST_URL, status=200)
            resp = await client.get(TEST_URL, headers=additional_headers)
            self.assertEqual(HTTPStatus.OK, resp.status)

            req = rsps.requests.get(("get", URL(TEST_URL)))
            expected_headers = {**additional_headers}
            self.assertEqual(expected_headers, req[0].kwargs.get("headers"))

    async def test_client_always_has_default_timeout_configured(self):

        client = HttpClient()
        client.session_class = self.session_class_mock

        await client.get(TEST_URL)

        client.session_class.assert_called_with(
            timeout=default_http_client_timeout,
            headers=ANY,
            raise_for_status=True,
        )

    async def test_can_choose_a_different_timeout_on_client_instantiation(self):
        new_timeout = ClientTimeout(total=2, connect=5)
        client = HttpClient(timeout=new_timeout)
        client.session_class = self.session_class_mock

        await client.get(TEST_URL)

        client.session_class.assert_called_with(
            timeout=new_timeout, headers=ANY, raise_for_status=True
        )

        client._session.request.assert_awaited_with(
            "get",
            ANY,
            timeout=None,
            headers=ANY,
            allow_redirects=True,
            raise_for_status=True,
        )

    async def test_can_override_timeout_passing_a_new_timeout_on_the_request(
        self
    ):
        """
        client.get(..., timeout=ClientTimeout(...))
        """
        timeout = ClientTimeout(connect=1, total=5)
        client = HttpClient()
        client.session_class = self.session_class_mock

        await client.get(TEST_URL, timeout=timeout)
        client._session.request.assert_awaited_with(
            "get",
            ANY,
            timeout=timeout,
            headers=ANY,
            allow_redirects=True,
            raise_for_status=True,
        )

    async def test_can_override_option_to_automatically_raise_when_request_fails(
        self
    ):
        timeout = ClientTimeout(connect=1, total=5)
        client = HttpClient()
        client.session_class = self.session_class_mock

        await client.get(TEST_URL, raise_for_status=False)
        client._session.request.assert_awaited_with(
            "get",
            ANY,
            timeout=ANY,
            headers=ANY,
            raise_for_status=False,
            allow_redirects=True,
        )

    async def test_exceptions_have_detail_info_about_the_request_that_failed(
        self
    ):
        """
        Cada exceção lançada deve carregar algumas infos sobre o request original.
        A ClientResponseError da aiohttp tem tudo que queremos.

        A exception lançada pelo client contém:
          - request_info original
          - status (int)
        """
        client = HttpClient()
        url = "https://httpbin.org/status/404"

        try:
            await client.get(url)
        except HTTPNotFound as e:
            self.assertEqual(HTTPStatus.NOT_FOUND, e.status)
            self.assertEqual(url, str(e.request_info.url))
            self.assertEqual("GET", e.request_info.method)
            self.assertIsNotNone(e.request_info.headers)

    async def test_raise_internal_error_exception_when_response_is_500(self):
        client = HttpClient()
        url = "https://httpbin.org/status/500"

        try:
            await client.get(url)
        except HTTPInternalServerError as e:
            self.assertEqual(HTTPStatus.INTERNAL_SERVER_ERROR, e.status)
            self.assertEqual(url, str(e.request_info.url))
            self.assertEqual("GET", e.request_info.method)
            self.assertIsNotNone(e.request_info.headers)

    async def test_raise_bad_request_exception_when_response_is_400(self):
        client = HttpClient()
        url = "https://httpbin.org/status/400"

        try:
            await client.get(url)
        except HTTPBadRequest as e:
            self.assertEqual(HTTPStatus.BAD_REQUEST, e.status)
            self.assertEqual(url, str(e.request_info.url))
            self.assertEqual("GET", e.request_info.method)
            self.assertIsNotNone(e.request_info.headers)

    async def test_re_raise_original_exception(self):
        """
        Se o request lançar uma exception que não estamos tratando, devemos re-lançar.
        """
        client = HttpClient()
        url = "https://httpbin.org/status/415"

        try:
            await client.get(url)
        except ClientResponseError as e:
            self.assertEqual(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, e.status)
            self.assertEqual(url, str(e.request_info.url))
            self.assertEqual("GET", e.request_info.method)
            self.assertIsNotNone(e.request_info.headers)

    async def test_always_make_request_with_follow_redirect(self):
        """
        Seguimos redirect por padrão
        """
        client = HttpClient()
        client.session_class = self.session_class_mock

        await client.get(TEST_URL)
        client._session.request.assert_called_with(
            "get",
            TEST_URL,
            timeout=ANY,
            headers=ANY,
            allow_redirects=True,
            raise_for_status=True,
        )

    async def test_post(self):
        expected_headers = {"X-Header": "Value"}
        timeout = ClientTimeout(connect=5, total=10)
        client = HttpClient()
        client.session_class = self.session_class_mock

        await client.post(TEST_URL, timeout=timeout, headers=expected_headers)
        client._session.request.assert_awaited_with(
            "post",
            TEST_URL,
            timeout=timeout,
            headers=expected_headers,
            raise_for_status=True,
            allow_redirects=True,
        )

    async def test_get(self):
        expected_headers = {"X-Header": "Value"}
        timeout = ClientTimeout(connect=5, total=10)
        client = HttpClient()
        client.session_class = self.session_class_mock

        await client.get(TEST_URL, timeout=timeout, headers=expected_headers)
        client._session.request.assert_awaited_with(
            "get",
            TEST_URL,
            timeout=timeout,
            headers=expected_headers,
            raise_for_status=True,
            allow_redirects=True,
        )

    async def test_put(self):
        expected_headers = {"X-Header": "Value"}
        timeout = ClientTimeout(connect=5, total=10)
        client = HttpClient()
        client.session_class = self.session_class_mock

        await client.put(TEST_URL, timeout=timeout, headers=expected_headers)
        client._session.request.assert_awaited_with(
            "put",
            TEST_URL,
            timeout=timeout,
            headers=expected_headers,
            raise_for_status=True,
            allow_redirects=True,
        )

    async def test_patch(self):
        expected_headers = {"X-Header": "Value"}
        timeout = ClientTimeout(connect=5, total=10)
        client = HttpClient()
        client.session_class = self.session_class_mock

        await client.patch(TEST_URL, timeout=timeout, headers=expected_headers)
        client._session.request.assert_awaited_with(
            "patch",
            TEST_URL,
            timeout=timeout,
            headers=expected_headers,
            raise_for_status=True,
            allow_redirects=True,
        )

    async def test_delete(self):
        expected_headers = {"X-Header": "Value"}
        timeout = ClientTimeout(connect=5, total=10)
        client = HttpClient()
        client.session_class = self.session_class_mock

        await client.delete(TEST_URL, timeout=timeout, headers=expected_headers)
        client._session.request.assert_awaited_with(
            "delete",
            TEST_URL,
            timeout=timeout,
            headers=expected_headers,
            raise_for_status=True,
            allow_redirects=True,
        )
