import array
import ast
import asyncio
import logging
import json
import math
import warnings
from json import JSONDecodeError
from threading import Thread
from datetime import datetime
from azure.iot.device.common.pipeline.pipeline_exceptions import PipelineNotRunning
import numpy as np

import URBasic
from cloud.control_task.cobot_control_task import CobotControlTask
from cloud.iot_task.cobot_iot_task import CobotIotTask
from cloud.device import Device
import xml.etree.ElementTree as ET
import time

from model.joint_position_model import JointPositionModel
from model.move_j_control_model import MoveJControlModel
from model.move_l_control_model import MoveLControlModel
from model.move_p_control_model import MovePControlModel


class Cobot(object):
    def __init__(self,
                 rtde_host,
                 rtde_port,
                 control_configuration_path,
                 cobot_client_configuration_path,
                 model_id,
                 provisioning_host,
                 id_scope,
                 registration_id,
                 symmetric_key):
        self.__rtde_host = rtde_host
        self.__rtde_port = rtde_port
        self.__control_configuration_path = control_configuration_path
        self.__cobot_client_configuration_path = cobot_client_configuration_path
        self.__model_id = model_id
        self.__provisioning_host = provisioning_host
        self.__id_scope = id_scope
        self.__registration_id = registration_id
        self.__symmetric_key = symmetric_key

        self.__cobot_device = None
        self.__ur_script_ext = None

        self.__cobot_control_task = None
        self.__cobot_iot_task = None

        self.__ur_script_ext_control_thread = None
        self.__cobot_control_thread = None
        self.__cobot_iot_thread = None

        self.__cobot_control_lock = True
        self.__cobot_iot_lock = True

    def stdin_listener(self):
        while True:
            config_element_tree = ET.parse(self.__cobot_client_configuration_path)
            cobot_configuration = config_element_tree.find('cobot')
            process_continue = cobot_configuration.find('status').text
            if process_continue == "False":
                logging.info("cobot.stdin_listener:break process_continue={process_continue}"
                             .format(process_continue=process_continue))
                break
            else:
                time.sleep(1)

    def move_j_control_task_callback(self, move_j_control_model):
        if not self.__cobot_control_lock:
            logging.info("cobot.move_j_control_task_callback:__cobot_control_lock={cobot_control_lock}"
                         .format(cobot_control_lock=self.__cobot_control_lock))
            self.__cobot_control_lock = True

            self.__cobot_control_task = CobotControlTask(robot=self.__ur_script_ext)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.__cobot_control_task.move_j(move_j_control_model=move_j_control_model))
                logging.info('cobot.move_j_control_task_callback:Thread success')
            except RuntimeError:
                logging.error('cobot.move_j_control_task_callback:Thread failed runtime_error={runtime_error}'
                              .format(runtime_error=RuntimeError.__dict__))
            logging.info('cobot.move_j_control_task_callback:Close')
            loop.close()
            self.__cobot_control_lock = False
        else:
            logging.error("cobot.move_j_control_task_callback:__cobot_control_lock={cobot_control_lock}"
                          .format(cobot_control_lock=self.__cobot_control_lock))
            self.__cobot_control_lock = False

    async def move_j_control_command_handler(self, values):
        try:
            move_j_control_model = MoveJControlModel.get_move_j_model_from_values(values)
            logging.info("cobot.move_j_control_command_handler:Success "
                         "move_j_control_model={move_j_control_model} "
                         "type={type}"
                         .format(move_j_control_model=move_j_control_model.__dict__,
                                 type=str(type(move_j_control_model))))
            self.__cobot_control_thread = Thread(target=self.move_j_control_task_callback, args=(move_j_control_model,))
            self.__cobot_control_thread.start()
        except JSONDecodeError:
            logging.error("cobot.move_j_control_command_handler:Failed error=JSONDecodeError")

    @staticmethod
    def move_j_control_response_handler(values):
        response_dict = {
            "StartTime": datetime.now().isoformat()
        }
        response_payload = json.dumps(response_dict, default=lambda o: o.__dict__, sort_keys=True)
        logging.info("cobot.move_j_control_response_handler:Response response_payload={response_payload}"
                     .format(response_payload=values))
        return response_payload

    def move_p_control_task_callback(self, move_p_control_model):
        if not self.__cobot_control_lock:
            logging.info("cobot.move_p_control_task_callback:__cobot_control_lock={cobot_control_lock}"
                         .format(cobot_control_lock=self.__cobot_control_lock))
            self.__cobot_control_lock = True
            logging.info("cobot.move_p_control_task_callback:Robot initialised")

            self.__cobot_control_task = CobotControlTask(robot=self.__ur_script_ext)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.__cobot_control_task.move_p(move_p_control_model=move_p_control_model))
                logging.info('cobot.move_p_control_task_callback:Thread completed')
            except RuntimeError:
                logging.error('cobot.move_p_control_task_callback:Thread failed runtime_error={runtime_error}'
                              .format(runtime_error=RuntimeError.__dict__))
            logging.info('cobot.move_p_control_task_callback:Close')
            loop.close()
            self.__cobot_control_lock = False
        else:
            logging.error("cobot.move_p_control_task_callback:__cobot_control_lock={cobot_control_lock}"
                          .format(cobot_control_lock=self.__cobot_control_lock))
            self.__cobot_control_lock = False

    async def move_p_control_command_handler(self, values):
        move_p_control_model = MovePControlModel.get_move_p_model_from_values(values)

        logging.info("cobot.move_p_control_command_handler:Success "
                     "move_p_control_model={move_p_control_model} "
                     "type={type}"
                     .format(move_p_control_model=move_p_control_model.__dict__,
                             type=str(type(move_p_control_model))))
        self.__cobot_control_thread = Thread(target=self.move_p_control_task_callback, args=(move_p_control_model,))
        self.__cobot_control_thread.start()

    @staticmethod
    def move_p_control_response_handler(values):
        response_dict = {
            "StartTime": datetime.now().isoformat()
        }
        response_payload = json.dumps(response_dict, default=lambda o: o.__dict__, sort_keys=True)
        logging.info("cobot.move_p_control_response_handler:Response response_payload={response_payload}"
                     .format(response_payload=values))
        return response_payload

    def move_l_control_task_callback(self, move_l_control_model):
        if not self.__cobot_control_lock:
            logging.info("cobot.move_l_control_task_callback:__cobot_control_lock={cobot_control_lock}"
                         .format(cobot_control_lock=self.__cobot_control_lock))
            self.__cobot_control_lock = True

            logging.info("cobot.move_l_control_task_callback:Robot initialised")

            self.__cobot_control_task = CobotControlTask(robot=self.__ur_script_ext)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.__cobot_control_task.move_l(move_l_control_model=move_l_control_model))
                logging.info('cobot.move_l_control_task_callback:Thread completed')
            except RuntimeError:
                logging.error('cobot.move_l_control_task_callback:Thread failed runtime_error={runtime_error}'
                              .format(runtime_error=RuntimeError.__dict__))
            logging.info('cobot.move_l_control_task_callback:Close')

            loop.close()
            self.__cobot_control_lock = False
        else:
            logging.error("cobot.move_l_control_task_callback:__cobot_control_lock={cobot_control_lock}"
                          .format(cobot_control_lock=self.__cobot_control_lock))
            self.__cobot_control_lock = False

    async def move_l_control_command_handler(self, values):
        move_l_control_model = MoveLControlModel.get_move_l_model_from_values(values)

        logging.info("cobot.move_l_control_command_handler:Success "
                     "move_l_control_model={move_l_control_model} "
                     "type={type}"
                     .format(move_l_control_model=move_l_control_model.__dict__,
                             type=str(type(move_l_control_model))))
        self.__cobot_control_thread = Thread(target=self.move_l_control_task_callback, args=(move_l_control_model,))
        self.__cobot_control_thread.start()

    @staticmethod
    def move_l_control_response_handler(values):
        response_dict = {
            "StartTime": datetime.now().isoformat()
        }
        response_payload = json.dumps(response_dict, default=lambda o: o.__dict__, sort_keys=True)
        logging.info("cobot.move_l_control_response_handler:Response response_payload={response_payload}"
                     .format(response_payload=values))
        return response_payload


    async def enable_control_command_handler(self, values):
        logging.info("cobot.enable_control_command_handler:Starting")
        robotModel = URBasic.robotModel.RobotModel()
        self.__ur_script_ext = URBasic.urScriptExt.UrScriptExt(host=self.__rtde_host, robotModel=robotModel)
        self.__ur_script_ext.reset_error()
        self.__cobot_control_lock = False
        logging.info("cobot.enable_control_command_handler:Executed")

    @staticmethod
    def enable_control_response_handler(values):
        response_dict = {
            "StartTime": datetime.now().isoformat()
        }
        response_payload = json.dumps(response_dict, default=lambda o: o.__dict__, sort_keys=True)
        logging.info("cobot.enable_control_response_handler:Response response_payload={response_payload}"
                     .format(response_payload=values))
        return response_payload

    async def disable_control_command_handler(self, values):
        logging.info("cobot.disable_control_command_handler:Starting")
        self.__ur_script_ext.close()
        self.__cobot_control_lock = True
        self.__ur_script_ext_control_thread.join()
        logging.info("cobot.disable_control_command_handler:Executed")

    @staticmethod
    def disable_control_response_handler(values):
        response_dict = {
            "StartTime": datetime.now().isoformat()
        }
        response_payload = json.dumps(response_dict, default=lambda o: o.__dict__, sort_keys=True)
        logging.info("cobot.disable_control_response_handler:Response response_payload={response_payload}"
                     .format(response_payload=values))
        return response_payload

    async def pause_control_command_handler(self, values):
        logging.info("cobot.pause_control_command_handler:Starting")
        self.__ur_script_ext.pause()
        self.__cobot_control_lock = True
        logging.info("cobot.pause_control_response_handler:Executed")

    @staticmethod
    def pause_control_response_handler(values):
        response_dict = {
            "StartTime": datetime.now().isoformat()
        }
        response_payload = json.dumps(response_dict, default=lambda o: o.__dict__, sort_keys=True)
        logging.info("cobot.pause_control_response_handler:Response response_payload={response_payload}"
                     .format(response_payload=values))
        return response_payload

    async def play_control_command_handler(self, values):
        logging.info("cobot.play_control_command_handler:Starting")
        self.__ur_script_ext.play()
        self.__cobot_control_lock = False
        logging.info("cobot.play_control_command_handler:Executed")

    @staticmethod
    def play_control_response_handler(values):
        response_dict = {
            "StartTime": datetime.now().isoformat()
        }
        response_payload = json.dumps(response_dict, default=lambda o: o.__dict__, sort_keys=True)
        logging.info("cobot.play_control_command_handler:Response response_payload={response_payload}"
                     .format(response_payload=values))
        return response_payload

    async def close_safety_popup_control_command_handler(self, values):
        logging.info("cobot.close_safety_popup_control_command_handler:Starting")
        self.__ur_script_ext.close_safety_popup()
        self.__cobot_control_lock = False
        logging.info("cobot.close_safety_popup_control_command_handler:Executed")

    @staticmethod
    def close_safety_popup_control_response_handler(values):
        response_dict = {
            "StartTime": datetime.now().isoformat()
        }
        response_payload = json.dumps(response_dict, default=lambda o: o.__dict__, sort_keys=True)
        logging.info("cobot.close_safety_popup_control_response_handler:Response response_payload={response_payload}"
                     .format(response_payload=values))
        return response_payload

    async def unlock_protective_stop_control_command_handler(self, values):
        logging.info("cobot.unlock_protective_stop_control_command_handler:Starting")
        self.__ur_script_ext.unlock_protective_stop()
        self.__cobot_control_lock = False
        logging.info("cobot.unlock_protective_stop_control_command_handler:Executed")

    @staticmethod
    def unlock_protective_stop_control_response_handler(values):
        response_dict = {
            "StartTime": datetime.now().isoformat()
        }
        response_payload = json.dumps(response_dict, default=lambda o: o.__dict__, sort_keys=True)
        logging.info("cobot.unlock_protective_stop_control_response_handler:"
                     "Response response_payload={response_payload}"
                     .format(response_payload=values))
        return response_payload

    # async def stop_cobot_control_command_handler(self, values):
    #     if values:
    #         logging.info("cobot.stop_cobot_control_command_handler:cobot_control_lock={cobot_control_lock}"
    #                      .format(cobot_control_lock=self.__cobot_control_lock))
    #         self.__cobot_control_lock = True
    #         logging.info("cobot.stop_cobot_control_command_handler:values={values} type={type}"
    #                      .format(values=values, type=str(type(values))))
    #         self.__cobot_control_task.terminate()
    #         self.__cobot_control_thread.join()
    #
    # @staticmethod
    # def stop_cobot_control_command_response_handler(values):
    #     response_dict = {
    #         "StopTime": datetime.now().isoformat()
    #     }
    #     response_payload = json.dumps(response_dict, default=lambda o: o.__dict__, sort_keys=True)
    #     return response_payload

    # def start_cobot_iot_task_callback(self, values):
    #     if self.__cobot_iot_lock:
    #         try:
    #             logging.info("cobot.cobot_iot_task_callback:__cobot_iot_lock={cobot_iot_lock}"
    #                          .format(cobot_iot_lock=self.__cobot_iot_lock))
    #             self.__cobot_iot_lock = False
    #             self.__cobot_iot_task = CobotIotTask(self.__cobot_device)
    #             loop = asyncio.new_event_loop()
    #             asyncio.set_event_loop(loop)
    #             loop.run_until_complete(self.__cobot_iot_task.connect())
    #             loop.close()
    #         except PipelineNotRunning:
    #             logging.error("cobot.cobot_iot_task_callback:PipelineNotRunning")
    #
    #
    #     else:
    #         logging.error("cobot.cobot_iot_task_callback:__cobot_iot_lock={cobot_iot_lock}"
    #                       .format(cobot_iot_lock=self.__cobot_iot_lock))

    # async def start_cobot_iot_command_handler(self, values):
    #     if values:
    #         logging.info("cobot.start_cobot_iot_command_handler:values={values} type={type}"
    #                      .format(values=values, type=str(type(values))))
    #         self.__cobot_iot_thread = Thread(target=self.start_cobot_iot_task_callback, args=(values,))
    #         self.__cobot_iot_thread.start()

    # @staticmethod
    # def start_cobot_iot_command_response_handler(values):
    #     response_dict = {
    #         "StartTime": datetime.now().isoformat()
    #     }
    #     response_payload = json.dumps(response_dict, default=lambda o: o.__dict__, sort_keys=True)
    #     return response_payload
    #
    # async def stop_cobot_iot_command_handler(self, values):
    #     if not self.__cobot_iot_lock:
    #         self.__cobot_iot_lock = True
    #         logging.info("cobot.stop_cobot_iot_command_handler:values={values} type={type}"
    #                      .format(values=values, type=str(type(values))))
    #         self.__cobot_iot_task.terminate()
    #         self.__cobot_iot_thread.join()
    #
    # @staticmethod
    # def stop_cobot_iot_command_response_handler(values):
    #     response_dict = {
    #         "StopTime": datetime.now().isoformat()
    #     }
    #     response_payload = json.dumps(response_dict, default=lambda o: o.__dict__, sort_keys=True)
    #     return response_payload

    async def connect_azure_iot(self, queue):
        self.__cobot_device = Device(model_id=self.__model_id,
                                     provisioning_host=self.__provisioning_host,
                                     id_scope=self.__id_scope,
                                     registration_id=self.__registration_id,
                                     symmetric_key=self.__symmetric_key)

        await self.__cobot_device.create_iot_hub_device_client()

        await self.__cobot_device.iot_hub_device_client.connect()

        command_listeners = asyncio.gather(
            self.__cobot_device.execute_command_listener(
                method_name="EnableControlCommand",
                user_command_handler=self.enable_control_command_handler,
                create_user_response_handler=self.enable_control_response_handler,
            ),
            self.__cobot_device.execute_command_listener(
                method_name="DisableControlCommand",
                user_command_handler=self.disable_control_command_handler,
                create_user_response_handler=self.disable_control_response_handler,
            ),
            self.__cobot_device.execute_command_listener(
                method_name="MoveJControlCommand",
                user_command_handler=self.move_j_control_command_handler,
                create_user_response_handler=self.move_j_control_response_handler,
            ),
            self.__cobot_device.execute_command_listener(
                method_name="MovePControlCommand",
                user_command_handler=self.move_p_control_command_handler,
                create_user_response_handler=self.move_p_control_response_handler,
            ),
            self.__cobot_device.execute_command_listener(
                method_name="MoveLControlCommand",
                user_command_handler=self.move_l_control_command_handler,
                create_user_response_handler=self.move_l_control_response_handler,
            ),
            self.__cobot_device.execute_command_listener(
                method_name="PauseControlCommand",
                user_command_handler=self.pause_control_command_handler,
                create_user_response_handler=self.pause_control_response_handler,
            ),
            self.__cobot_device.execute_command_listener(
                method_name="PlayControlCommand",
                user_command_handler=self.play_control_command_handler,
                create_user_response_handler=self.play_control_response_handler,
            ),
            self.__cobot_device.execute_command_listener(
                method_name="CloseSafetyPopupControlCommand",
                user_command_handler=self.close_safety_popup_control_command_handler,
                create_user_response_handler=self.close_safety_popup_control_response_handler,
            ),
            self.__cobot_device.execute_command_listener(
                method_name="UnlockProtectiveStopControlCommand",
                user_command_handler=self.unlock_protective_stop_control_command_handler,
                create_user_response_handler=self.unlock_protective_stop_control_response_handler,
            ),
            # self.__cobot_device.execute_command_listener(
            #     method_name="StopCobotCommand",
            #     user_command_handler=self.stop_cobot_control_command_handler,
            #     create_user_response_handler=self.stop_cobot_control_command_response_handler,
            # ),
            # self.__cobot_device.execute_command_listener(
            #     method_name="StartIotCommand",
            #     user_command_handler=self.start_cobot_iot_command_handler,
            #     create_user_response_handler=self.start_cobot_iot_command_response_handler,
            # ),
            # self.__cobot_device.execute_command_listener(
            #     method_name="StopIotCommand",
            #     user_command_handler=self.stop_cobot_iot_command_handler,
            #     create_user_response_handler=self.stop_cobot_iot_command_response_handler,
            # ),
            self.__cobot_device.execute_property_listener(),
        )

        loop = asyncio.get_running_loop()
        user_finished = loop.run_in_executor(None, self.stdin_listener)

        await user_finished

        if not command_listeners.done():
            command_listeners.set_result(["Cobot done"])

        command_listeners.cancel()

        await self.__cobot_device.iot_hub_device_client.shutdown()
        logging.info("cobot.connect_azure_iot:queue.put")
        await queue.put(None)

    @staticmethod
    def check_valid_literal(values):
        try:
            result = ast.literal_eval(values)
            if len(result) == 6:
                logging.info("cobot.check_valid_literal:Valid result={result} type={type}"
                             .format(result=result, type=str(type(values))))
                return True
            else:
                logging.info(
                    "cobot.check_valid_literal:Invalid result=Length should be minimum 6 values length={length}"
                    .format(length=str(len(result))))
                return False
        except (ValueError, SyntaxError) as e:
            logging.info("cobot.check_valid_literal:Invalid values={values} type={type} error={error}"
                         .format(values=values, type=str(type(values)), error=str(e)))
            return False
