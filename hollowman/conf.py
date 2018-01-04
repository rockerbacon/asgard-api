import os
import base64

from marathon import MarathonClient
from hollowman.options import get_option

ENABLED = "1"
DISABLED = "0"

MARATHON_CREDENTIALS = os.getenv("MARATHON_CREDENTIALS", "guest:guest")
MARATHON_AUTH_HEADER = "Basic {}".format(base64.b64encode(MARATHON_CREDENTIALS.encode("utf-8")).decode('utf-8'))
MARATHON_ENDPOINT = os.getenv("MARATHON_ENDPOINT", "http://127.0.0.1:8080")
DEFAULT_MARATHON_ADDRESS = "http://127.0.0.1:8080"


def _build_cors_whitelist(env_value):
    if not env_value:
        return []
    return [_host.strip() for _host in env_value.split(",") if _host.strip()]

def _build_marathon_addresses():
    addresses = {addr.rstrip("/") for addr in get_option("MARATHON", "ADDRESS")}
    final_addresses = sorted(list(addresses))
    if not final_addresses:
        final_addresses = [DEFAULT_MARATHON_ADDRESS]
    return final_addresses

MARATHON_ADDRESSES = _build_marathon_addresses()
MARATHON_LEADER = MARATHON_ADDRESSES[0]

user, passw = MARATHON_CREDENTIALS.split(':')
marathon_client = MarathonClient(MARATHON_ADDRESSES, username=user, password=passw)

CORS_WHITELIST = _build_cors_whitelist(os.getenv("HOLLOWMAN_CORS_WHITELIST"))

REDIRECT_ROOTPATH_TO = os.getenv("HOLLOWMAN_REDIRECT_ROOTPATH_TO", "/v2/apps")
GOOGLE_OAUTH2_CLIENT_ID = os.getenv("HOLLOWMAN_GOOGLE_OAUTH2_CLIENT_ID", "client_id")
GOOGLE_OAUTH2_CLIENT_SECRET = os.getenv("HOLLOWMAN_GOOGLE_OAUTH2_CLIENT_SECRET", "client_secret")

SECRET_KEY = os.getenv("HOLLOWMAN_SECRET_KEY", "secret")
REDIRECT_AFTER_LOGIN = os.getenv("HOLLOWMAN_REDIRECT_AFTER_LOGIN")

HOLLOWMAN_DB_URL = os.getenv("HOLLOWMAN_DB_URL", "sqlite://")
HOLLOWMAN_DB_ECHO = os.getenv("HOLLOWMAN_DB_ECHO", DISABLED) == ENABLED

