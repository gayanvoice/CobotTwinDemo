# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------

import os
import msrest
from azure.iot.hub import IoTHubRegistryManager
from azure.iot.hub.models import Twin, TwinProperties
from azure.iot.hub.models import CloudToDeviceMethod

iothub_connection_str = "HostName=100638182IotHub.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=O" \
                        "/fpHPDkS+5/oU/Ob5v7fx8YahD0oUeesLTmLIXLkGw="
device_id = "Cobot"
method_name = "startCobotC" \
              "" \
              "ommand"

set_position_1 = [-0.12, -0.43, 0.14, 0, 3.11, 0.14]
set_position_2 = [-0.22, -0.71, 0.21, 0, 3.11, 0.24]
set_position_3 = [-0.82, -0.81, 0.31, 0, 3.21, 0.34]
set_position_4 = [-0.62, -0.91, 0.41, 0, 3.31, 0.54]
set_position_array = [set_position_1, set_position_2, set_position_3, set_position_4]

method_payload = set_position_array

# This sample shows how to use the IoT Hub Registry Manager for a PnP device using a "thermostat" example

# This sample creates and uses device with SAS authentication For other authentication types use the appropriate
# create and update APIs: X509: new_device = iothub_registry_manager.create_device_with_x509(device_id,
# primary_thumbprint, secondary_thumbprint, status) device_updated = iothub_registry_manager.update_device_with_X509(
# device_id, etag, primary_thumbprint, secondary_thumbprint, status) Certificate authority: new_device =
# iothub_registry_manager.create_device_with_certificate_authority(device_id, status) device_updated =
# iothub_registry_manager.update_device_with_certificate_authority(self, device_id, etag, status):
try:
    # Create IoTHubRegistryManager
    iothub_registry_manager = IoTHubRegistryManager.from_connection_string(iothub_connection_str)

    # Get device twin
    twin = iothub_registry_manager.get_twin(device_id)
    print("The device twin is: ")
    print("")
    print(twin)
    print("")

    # Print the device's model ID
    additional_props = twin.additional_properties
    if "modelId" in additional_props:
        print("The Model ID for this device is:")
        print(additional_props["modelId"])
        print("")

    # Update twin
    twin_patch = Twin()
    twin_patch.properties = TwinProperties(
        desired={"targetTemperature": 42}
    )  # this is relevant for the thermostat device sample
    updated_twin = iothub_registry_manager.update_twin(device_id, twin_patch, twin.etag)
    print("The twin patch has been successfully applied")
    print("")

    # invoke device method
    device_method = CloudToDeviceMethod(method_name=method_name, payload=method_payload)
    iothub_registry_manager.invoke_device_method(device_id, device_method)
    print("The device method has been successfully invoked")
    print("")

    # Set registry manager object to `None` so all open files get closed
    iothub_registry_manager = None

except msrest.exceptions.HttpOperationError as ex:
    print("HttpOperationError error {0}".format(ex.response.text))
except Exception as ex:
    print("Unexpected error {0}".format(ex))
except KeyboardInterrupt:
    print("{} stopped".format(__file__))
finally:
    print("{} finished".format(__file__))