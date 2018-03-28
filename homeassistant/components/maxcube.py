"""
Platform for the MAX! Cube LAN Gateway.

For more details about this component, please refer to the documentation
https://home-assistant.io/components/maxcube/
"""
import logging
import time
from socket import timeout
from threading import Lock

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.const import CONF_HOST, CONF_PORT

REQUIREMENTS = ['maxcube-api==0.1.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 62910
DOMAIN = 'maxcube'

DATA_KEY = 'maxcube'

NOTIFICATION_ID = 'maxcube_notification'
NOTIFICATION_TITLE = 'Max!Cube gateway setup'

CONF_GATEWAYS = 'gateways'

CONFIG_GATEWAY = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_GATEWAYS, default={}):
            vol.All(cv.ensure_list, [CONFIG_GATEWAY])
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Establish connection to MAX! Cube."""
    from maxcube.connection import MaxCubeConnection
    from maxcube.cube import MaxCube
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    if DOMAIN not in config:
        return False

    gateways = config[DOMAIN][CONF_GATEWAYS]
    for gateway in gateways:
        host = gateway[CONF_HOST]
        port = gateway[CONF_PORT]

        try:
            cube = MaxCube(MaxCubeConnection(host, port))
            hass.data[DATA_KEY][host] = MaxCubeHandle(cube)
        except timeout as ex:
            _LOGGER.error("Unable to connect to Max!Cube gateway: %s", str(ex))
            hass.components.persistent_notification.create(
                'Error: {}<br />'
                'You will need to restart Home Assistant after fixing.'
                ''.format(ex),
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)
            return False

    load_platform(hass, 'climate', DOMAIN)
    load_platform(hass, 'binary_sensor', DOMAIN)

    return True


class MaxCubeHandle(object):
    """Keep the cube instance in one place and centralize the update."""

    def __init__(self, cube):
        """Initialize the Cube Handle."""
        self.cube = cube
        self.mutex = Lock()
        self._updatets = time.time()

    def update(self):
        """Pull the latest data from the MAX! Cube."""
        # Acquire mutex to prevent simultaneous update from multiple threads
        with self.mutex:
            # Only update every 60s
            if (time.time() - self._updatets) >= 60:
                _LOGGER.debug("Updating")

                try:
                    self.cube.update()
                except timeout:
                    _LOGGER.error("Max!Cube connection failed")
                    return False

                self._updatets = time.time()
            else:
                _LOGGER.debug("Skipping update")
