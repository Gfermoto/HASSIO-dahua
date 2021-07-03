"""Adds config flow (UI flow) for Dahua IP cameras."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers import config_validation as cv

from . import DahuaRpc2Client
from .client import DahuaClient
from .const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_ADDRESS,
    CONF_RTSP_PORT,
    CONF_PORT,
    CONF_STREAMS,
    CONF_EVENTS,
    CONF_NAME,
    STREAM_MAIN,
    STREAM_SUB,
    STREAM_BOTH,
    DOMAIN,
    PLATFORMS,
)

"""
https://developers.home-assistant.io/docs/config_entries_config_flow_handler
https://developers.home-assistant.io/docs/data_entry_flow_index/
"""

_LOGGER: logging.Logger = logging.getLogger(__package__)

STREAMS = [STREAM_MAIN, STREAM_SUB, STREAM_BOTH]

DEFAULT_EVENTS = ["VideoMotion", "CrossLineDetection", "AlarmLocal", "VideoLoss", "VideoBlind"]

ALL_EVENTS = ["VideoMotion",
              "VideoLoss",
              "AlarmLocal",
              "CrossLineDetection",
              "AudioAnomaly",
              "AudioMutation",
              "VideoMotionInfo",
              "SmartMotionHuman",
              "SmartMotionVehicle",
              "NewFile",
              "VideoBlind",
              "IntelliFrame",
              "CrossRegionDetection",
              "LeftDetection",
              "TakenAwayDetection",
              "VideoAbnormalDetection",
              "FaceDetection",
              "VideoUnFocus",
              "WanderDetection",
              "RioterDetection",
              "ParkingDetection",
              "MoveDetection",
              "StorageNotExist",
              "StorageFailure",
              "StorageLowSpace",
              "AlarmOutput",
              "InterVideoAccess",
              "NTPAdjustTime",
              "TimeChange",
              "MDResult",
              "HeatImagingTemper",
              "CrowdDetection",
              "FireWarning",
              "FireWarningInfo",
              ]

"""
https://developers.home-assistant.io/docs/data_entry_flow_index
"""


class DahuaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Dahua Camera API."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self.dahua_config = {}
        self._errors = {}
        self.init_info = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user to add a camera."""
        self._errors = {}

        # Uncomment the next 2 lines if only a single instance of the integration is allowed:
        # if self._async_current_entries():
        #     return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            data = await self._test_credentials(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_ADDRESS],
                user_input[CONF_PORT],
                user_input[CONF_RTSP_PORT],
            )
            if data is not None:
                # Only allow a camera to be setup once
                if "serialNumber" in data and data["serialNumber"] is not None:
                    await self.async_set_unique_id(data["serialNumber"])
                    self._abort_if_unique_id_configured()

                user_input[CONF_NAME] = data["name"]
                self.init_info = user_input
                return await self._show_config_form_name(user_input)
            else:
                self._errors["base"] = "auth"

        return await self._show_config_form_user(user_input)

    async def async_step_name(self, user_input=None):
        """Handle a flow to configure the camera name."""
        self._errors = {}

        if user_input is not None:
            if self.init_info is not None:
                self.init_info.update(user_input)
                return self.async_create_entry(
                    title=self.init_info["name"],
                    data=self.init_info,
                )

        return await self._show_config_form_name(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DahuaOptionsFlowHandler(config_entry)

    async def _show_config_form_user(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit camera name."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_ADDRESS): str,
                    vol.Required(CONF_PORT, default="80"): str,
                    vol.Required(CONF_RTSP_PORT, default="554"): str,
                    vol.Required(CONF_STREAMS, default=STREAMS[0]): vol.In(STREAMS),
                    vol.Optional(CONF_EVENTS, default=DEFAULT_EVENTS): cv.multi_select(ALL_EVENTS),
                }
            ),
            errors=self._errors,
        )

    async def _show_config_form_name(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="name",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                }
            ),
            errors=self._errors,
        )

    async def _test_credentials(self, username, password, address, port, rtsp_port):
        """Return true if credentials is valid."""
        try:
            session = async_create_clientsession(self.hass)
            client = DahuaRpc2Client(
                username, password, address, port, rtsp_port, session
            )
            await client.login()

            name = await client.get_device_name()
            serial = await client.get_serial_number()

            return {
                "name": name,
                "serialNumber": serial,
            }
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Could not connect to Dahua device", exc_info=exception)
            pass
        return None


class DahuaOptionsFlowHandler(config_entries.OptionsFlow):
    """Dahua config flow options handler."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(x, default=self.options.get(x, True)): bool
                    for x in sorted(PLATFORMS)
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.data.get(CONF_USERNAME), data=self.options
        )
