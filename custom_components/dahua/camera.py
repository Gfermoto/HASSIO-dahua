"""This component provides basic support for Dahua IP cameras."""

import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.components.camera import SUPPORT_STREAM, Camera

from custom_components.dahua import DahuaDataUpdateCoordinator
from custom_components.dahua.entity import DahuaBaseEntity


from .const import (
    CONF_STREAMS,
    DOMAIN,
    STREAM_MAIN,
    STREAM_SUB,
    STREAM_BOTH,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)

# This service handled setting the infrared mode on the camera to Off, Auto, or Manual... along with the brightness
SERVICE_SET_INFRARED_MODE = "set_infrared_mode"

# For now we'll only support 1 channel. I don't have any cams where I can test a second channel.
# I'm not really sure what channel 2 means anyways, it doesn't seem to be the substream.
CHANNEL = 1


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Add a Dahua IP camera from a config entry."""

    streams = config_entry.data[CONF_STREAMS]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    if streams in (STREAM_MAIN, STREAM_BOTH):
        async_add_entities(
            [
                DahuaCamera(
                    coordinator,
                    coordinator.client.to_subtype(STREAM_MAIN),
                    config_entry,
                )
            ]
        )

    if streams in (STREAM_SUB, STREAM_BOTH):
        async_add_entities(
            [
                DahuaCamera(
                    coordinator,
                    coordinator.client.to_subtype(STREAM_SUB),
                    config_entry,
                )
            ]
        )

    # https://developers.home-assistant.io/docs/dev_101_services/
    # This will expose a service to enable setting the cameras infrared light to Auto, Manual, and Off along with the brightness
    if coordinator.supports_infrared_light():
        # method_name is the method that will be called upon calling the service. It's defined below in the DahuaCamera class
        method_name = "async_set_infrared_mode"
        platform = entity_platform.async_get_current_platform()
        platform.async_register_entity_service(
            SERVICE_SET_INFRARED_MODE,
            {
                vol.Required("mode"): vol.In(
                    [
                        "On",  # Dahua uses Manual but that's akward so we'll use On and translate it before we call the Dahua API
                        "on",
                        "Off",
                        "off",
                        "Auto",
                        "auto",
                    ]),
                vol.Optional('brightness', default=100): vol.All(vol.Coerce(int), vol.Range(min=0, max=100))
            },
            method_name
        )


class DahuaCamera(DahuaBaseEntity, Camera):
    """An implementation of a Dahua IP camera."""

    def __init__(self, coordinator: DahuaDataUpdateCoordinator, stream_index: int, config_entry):
        """Initialize the Dahua camera."""
        DahuaBaseEntity.__init__(self, coordinator, config_entry)
        Camera.__init__(self)

        name = coordinator.client.to_stream_name(stream_index)
        self._name = "{0} {1}".format(config_entry.title, name)
        self._unique_id = coordinator.get_serial_number() + "_" + name
        self._stream_index = stream_index
        self._motion_status = False
        self._stream_source = coordinator.client.get_rtsp_stream_url(CHANNEL, stream_index)

    @ property
    def unique_id(self):
        """Return the entity unique ID."""
        return self._unique_id

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        # Send the request to snap a picture and return raw jpg data
        return await self.coordinator.client.async_get_snapshot(CHANNEL)

    @ property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_STREAM

    async def stream_source(self):
        """Return the RTSP stream source."""
        return self._stream_source

    @ property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return self.coordinator.is_motion_detection_enabled()

    async def async_enable_motion_detection(self):
        """Enable motion detection in camera."""
        try:
            await self.coordinator.client.enable_motion_detection(True)
            await self.coordinator.async_refresh()
        except TypeError:
            _LOGGER.debug("Failed enabling motion detection on '%s'. Is it supported by the device?", self._name)

    async def async_disable_motion_detection(self):
        """Disable motion detection."""
        try:
            await self.coordinator.client.enable_motion_detection(False)
            await self.coordinator.async_refresh()
        except TypeError:
            _LOGGER.debug("Failed disabling motion detection on '%s'. Is it supported by the device?", self._name)

    @ property
    def name(self):
        """Return the name of this camera."""
        return self._name

    async def async_set_infrared_mode(self, mode: str, brightness: int):
        """ Handles the service call from SERVICE_SET_INFRARED_MODE to set infrared mode and brightness """
        await self.coordinator.client.async_set_lighting_v1_mode(mode, brightness)
        await self.coordinator.async_refresh()
