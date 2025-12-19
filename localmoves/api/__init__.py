# Import all API endpoints to make them available for Frappe whitelist
from localmoves.api.dashboard import (
    get_system_configuration,
    update_system_configuration,
    get_pricing_configuration,
    update_pricing_configuration,
    get_vehicle_configuration,
    update_vehicle_configuration,
    get_multiplier_configuration,
    update_multiplier_configuration,
    # Other existing endpoints can be added here as needed
)


__all__ = [
    'get_system_configuration',
    'update_system_configuration',
    'get_pricing_configuration',
    'update_pricing_configuration',
    'get_vehicle_configuration',
    'update_vehicle_configuration',
    'get_multiplier_configuration',
    'update_multiplier_configuration',
]
