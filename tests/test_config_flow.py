"""Tests for config_flow.py."""

import inspect

from custom_components.mijnted.config_flow import (
    MijnTedConfigFlow,
    MijnTedOptionsFlowHandler,
)


class TestOptionsFlowFactory:
    """Verify the config flow options handler factory behavior."""

    def test_returns_options_flow_handler_directly(self):
        """Calling async_get_options_flow -> returns handler, not coroutine."""
        config_entry = object()

        handler = MijnTedConfigFlow.async_get_options_flow(config_entry)

        assert isinstance(handler, MijnTedOptionsFlowHandler)
        assert handler.config_entry is config_entry
        assert not inspect.iscoroutine(handler)
