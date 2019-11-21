from ora_backend import cache
from ora_backend.constants import CACHE_SETTINGS
from ora_backend.models import Setting
from ora_backend.utils.serialization import serialize_to_dict


async def get_latest_settings():
    settings = serialize_to_dict(await Setting.query.gino.all())
    return {setting["key"]: setting["value"] for setting in settings}


async def get_settings_from_cache():
    settings = await cache.get(CACHE_SETTINGS, namespace="settings")
    if settings is None:
        settings = await get_latest_settings()
        await cache.set(CACHE_SETTINGS, settings, namespace="settings")
        return settings

    return settings
